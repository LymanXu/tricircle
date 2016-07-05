# Copyright 2015 Huawei Technologies Co., Ltd.
# All Rights Reserved
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
from oslo_log import log

from neutron.api.v2 import attributes
from neutron.extensions import external_net
from neutron.plugins.ml2 import managers

from tricircle.common.i18n import _LI

LOG = log.getLogger(__name__)


class TricircleTypeManager(managers.TypeManager):

    def __init__(self):
        self.drivers = {}

        # NOTE(zhiyuan) here we call __init__ of super class's super class,
        # which is NamedExtensionManager's __init__ to bypass initialization
        # process of ml2 type manager
        super(managers.TypeManager, self).__init__(
            'tricircle.network.type_drivers',
            cfg.CONF.tricircle.type_drivers,
            invoke_on_load=True)
        LOG.info(_LI('Loaded type driver names: %s'), self.names())

        self._register_types()
        self._check_tenant_network_types(
            cfg.CONF.tricircle.tenant_network_types)

    def _register_types(self):
        for ext in self:
            network_type = ext.obj.get_type()
            if network_type not in self.drivers:
                self.drivers[network_type] = ext

    @staticmethod
    def _is_external_network(network):
        external = network.get(external_net.EXTERNAL)
        external_set = attributes.is_attr_set(external)
        if not external_set or not external:
            return False
        else:
            return True

    def create_network_segments(self, context, network, tenant_id):
        # NOTE(zhiyuan) before we figure out how to deal with external network
        # segment allocation, skip segment creation for external network
        if self._is_external_network(network):
            return
        segments = self._process_provider_create(network)
        session = context.session
        mtu = []
        with session.begin(subtransactions=True):
            network_id = network['id']
            if segments:
                for segment_index, segment in enumerate(segments):
                    segment = self.reserve_provider_segment(
                        session, segment)
                    self._add_network_segment(session, network_id, segment,
                                              mtu, segment_index)
            else:
                segment = self._allocate_tenant_net_segment(session)
                self._add_network_segment(session, network_id, segment, mtu)

    def extend_networks_dict_provider(self, context, networks):
        internal_networks = []
        for network in networks:
            # NOTE(zhiyuan) before we figure out how to deal with external
            # network segment allocation, skip external network since it does
            # not have segment information
            if not self._is_external_network(network):
                internal_networks.append(network)
        if internal_networks:
            super(TricircleTypeManager,
                  self).extend_networks_dict_provider(context,
                                                      internal_networks)