# Copyright 2016 Vsettan Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import re

from oslo_vmware import exceptions
from oslo_vmware import vim_util

try:
    from oslo_log import log
except ImportError:
    from neutron.openstack.common import log

from neutron.plugins.ml2.drivers.mech_dvs import config

LOG = log.getLogger(__name__)
CONF = config.CONF


class ResourceNotFoundException(exceptions.VimException):
    """Thrown when a resource can not be found."""
    pass


def build_pg_spec(session, name, vlan_tag):
    client_factory = session.vim.client.factory
    pg_spec = client_factory.create('ns0:DVPortgroupConfigSpec')
    pg_spec.name = name
    pg_spec.numPorts = 128
    pg_spec.type = 'ephemeral'
    DESCRIPTION = "Managed By Neutron"
    pg_spec.description = DESCRIPTION
    config = client_factory.create('ns0:VMwareDVSPortSetting')
    # Create the spec for the vlan tag
    spec_ns = 'ns0:VmwareDistributedVirtualSwitchVlanIdSpec'
    vlan_spec = client_factory.create(spec_ns)
    vlan_spec.vlanId = vlan_tag
    vlan_spec.inherited = '0'
    config.vlan = vlan_spec
    pg_spec.defaultPortConfig = config
    return pg_spec


def _get_net_name(network):
    name = network["name"][:40]
    uuid = network["id"]
    net_name = ("%s-%s" % (name, uuid) if name else uuid)
    # The length limit of a port group's name in vcenter is 80
    if len(net_name) > 80:
        suffix_len = len(uuid) + 1
        name_len_limit = 80 - suffix_len
        raise Exception(_("Network name '%s' is too long, "
                          "please limit your network name in "
                          "length %d.") % (name, name_len_limit))
    return net_name


def _get_raw_net_name(network):
    name = network["name"][:40]
    uuid = network["id"]
    net_name = ("%s-%s" % (name, uuid) if name else uuid)
    return net_name


def _get_object_by_type(results, type_value):
    """Get object by type.

    Get the desired object from the given objects
    result by the given type.
    """
    return [obj for obj in results
            if obj._type == type_value]


def get_datacenter(session):
    """Get the datacenter reference."""
    results = session.invoke_api(
        vim_util, 'get_objects', session.vim,
        "Datacenter", 100, ["name"])
    return results.objects[0].obj


def get_network_folder(session):
    """Get the network folder from datacenter."""
    dc_ref = get_datacenter(session)
    results = session.invoke_api(
        vim_util, 'get_object_property', session.vim,
        dc_ref, "networkFolder")
    return results


def get_dvs(session, dvs_name):
    """Get the dvs by name"""
    net_folder = get_network_folder(session)
    results = session.invoke_api(
        vim_util, 'get_object_property', session.vim,
        net_folder, "childEntity")
    networks = results.ManagedObjectReference
    dvswitches = _get_object_by_type(networks,
                                     "VmwareDistributedVirtualSwitch")
    dvs_ref = None
    for dvs in dvswitches:
        name = session.invoke_api(
            vim_util, 'get_object_property',
            session.vim, dvs,
            "name")
        if name == dvs_name:
            dvs_ref = dvs
            break

    if not dvs_ref:
        raise ResourceNotFoundException(_("Distributed Virtual Switch %s not "
                                          "found!"),
                                        dvs_name)
    else:
        LOG.info(_("Got distriubted virtual switch by name %s."),
                 dvs_name)

    return dvs_ref


def get_dvpg_by_name(session, dvpg_name):
    """Get the dvpg ref by name"""
    dc_ref = get_datacenter(session)
    net_list = session.invoke_api(
        vim_util, 'get_object_property', session.vim,
        dc_ref, "network").ManagedObjectReference
    type_value = "DistributedVirtualPortgroup"
    dvpg_list = _get_object_by_type(net_list, type_value)
    dvpg_ref = None
    for pg in dvpg_list:
        name = session.invoke_api(
            vim_util, 'get_object_property',
            session.vim, pg,
            "name")
        if dvpg_name == name:
            dvpg_ref = pg
            break

    if not dvpg_ref:
        LOG.warning(_("Distributed Port Group %s not found!"),
                    dvpg_name)
    else:
        LOG.info(_("Got distriubted port group by name %s."),
                 dvpg_name)

    return dvpg_ref


def create_dvpg(session, context):
    """Create a distributed virtual port group."""
    network = context.current
    segments = context.network_segments
    name = _get_net_name(network)
    net_type = segments[0]['network_type']
    if net_type != 'vlan':
        LOG.exception(_("VCenter does not support "
                        "network_type:%s, abort creating." % net_type))
        return
    vlan_id = segments[0]['segmentation_id'] or 0

    physical_network = segments[0]['physical_network']
    dvs_name = ""
    network_maps = CONF.ml2_vmware.network_maps
    for map in network_maps:
        physnet, dvswitch = map.split(":")
        if physnet == physical_network:
            dvs_name = dvswitch
            break
    if not dvs_name:
        raise Exception(_("No distributed virtual switch is "
                          "dedicated to create netowrk %s.") % name)

    LOG.info(_("Will create network %(name)s on distributed "
               "virtual switch %(dvs)s..."),
             {"name": name, "dvs": dvs_name})

    dvs_ref = get_dvs(session, dvs_name)
    pg_spec = build_pg_spec(session,
                            name,
                            vlan_id)
    pg_create_task = session.invoke_api(session.vim,
                                        "CreateDVPortgroup_Task",
                                        dvs_ref, spec=pg_spec)

    result = session.wait_for_task(pg_create_task)
    dvpg = result.result
    LOG.info(_("Network %(name)s created! \n%(pg_ref)s"),
             {"name": name, "pg_ref": dvpg})


def delete_dvpg(session, context):
    """Delete the distributed virtual port group."""
    network = context.current
    name = _get_raw_net_name(network)
    LOG.info(_("Will delete network %s..."), name)
    dvpg_ref = get_dvpg_by_name(session, name)
    if not dvpg_ref:
        LOG.warning(_("Network %s not present in vcenter, may be "
                      "deleted. Now remove network from neutron."),
                    name)
        return

    pg_delete_task = session.invoke_api(session.vim,
                                        "Destroy_Task",
                                        dvpg_ref)
    session.wait_for_task(pg_delete_task)
    LOG.info(_("Network %(name)s deleted."),
             {"name": name})


def update_dvpg(session, context):
    """Update the name of the given distributed virtual port group."""
    curr_net = context.current
    orig_net = context.original
    orig_name = _get_net_name(orig_net)
    dvpg_ref = get_dvpg_by_name(session, orig_name)
    rename_task = session.invoke_api(session.vim,
                                     "Rename_Task",
                                     dvpg_ref,
                                     newName=_get_net_name(curr_net))
    session.wait_for_task(rename_task)
    LOG.info(_("Network updated"))
