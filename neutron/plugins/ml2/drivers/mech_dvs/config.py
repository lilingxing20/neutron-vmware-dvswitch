# Copyright 2016 Vsettan Corp.
# All Rights Reserved.
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

from oslo_config import cfg


vmware_opts = [
    cfg.StrOpt(
        'host_ip',
        default='localhost',
        help='address of vcenter'),
    cfg.StrOpt(
        'host_username',
        default='administrator',
        help='username of vcenter server'),
    cfg.StrOpt(
        'host_password',
        default='password',
        help='password of vcenter server',
        secret=True),
    cfg.StrOpt(
        'wsdl_location',
        help='wsdl location'),
    cfg.FloatOpt(
        'task_poll_interval',
        default=2,
        help='task_poll_interval'),
    cfg.IntOpt(
        'api_retry_count',
        default=10,
        help='api_retry_count'),
    cfg.ListOpt(
        'network_maps',
        default=[],
        help='mappings between physical devices and dvs')
]

cfg.CONF.register_opts(vmware_opts, group='ml2_vmware')
CONF = cfg.CONF
CONF()
