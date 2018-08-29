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


from oslo_vmware import api as vmwareapi
from oslo_vmware import exceptions
try:
    from oslo_log import log
except ImportError:
    from neutron.openstack.common import log

from neutron.common import constants as n_const
from neutron.extensions import portbindings
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers.mech_dvs import config
from neutron.plugins.ml2.drivers.mech_dvs import vmware_util

LOG = log.getLogger(__name__)
CONF = config.CONF

portbindings.VIF_TYPE_DVS='dvs'


class VMwareDVSMechanismDriver(api.MechanismDriver):
    """Attach to networks using vmware agent.

    The VmwareMechanismDriver integrates the ml2 plugin with the
    vmware L2 agent. Port binding with this driver requires the vmware
    agent to be running on the port's host, and that agent to have
    connectivity to at least one segment of the port's network.
    """

    def initialize(self):
        LOG.info(_("VMware DVS mechanism driver initializing..."))
        self.vif_type = portbindings.VIF_TYPE_DVS
        self.vif_details = {portbindings.CAP_PORT_FILTER: False}
        self._create_session()
        LOG.info(_("VMware DVS mechanism driver initialized..."))

    def _create_session(self):
        """Create Vcenter Session for API Calling."""
        try:
            host_ip = CONF.ml2_vmware.host_ip
            host_username = CONF.ml2_vmware.host_username
            host_password = CONF.ml2_vmware.host_password
            wsdl_location = CONF.ml2_vmware.wsdl_location
            task_poll_interval = CONF.ml2_vmware.task_poll_interval
            api_retry_count = CONF.ml2_vmware.api_retry_count

            self._session = vmwareapi.VMwareAPISession(
                host_ip,
                host_username,
                host_password,
                api_retry_count,
                task_poll_interval,
                create_session=True,
                wsdl_loc=wsdl_location)
        except exceptions.VimConnectionException:
            LOG.error(_("Connection to vcenter %s failed"), host_ip)

    def create_network_precommit(self, context):
        vmware_util.create_dvpg(self._session,
                                context)

    def delete_network_precommit(self, context):
        vmware_util.delete_dvpg(self._session, context)

    def update_network_precommit(self, context):
        vmware_util.update_dvpg(self._session, context)

    def bind_port(self, context):
        LOG.debug("Attempting to bind port %(port)s on "
                  "network %(network)s",
                  {'port': context.current['id'],
                   'network': context.network.current['id']})
        for segment in context.network.network_segments:
            context.set_binding(segment[api.ID],
                                self.vif_type,
                                self.vif_details,
                                status=n_const.PORT_STATUS_ACTIVE)
