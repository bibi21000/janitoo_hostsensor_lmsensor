# -*- coding: utf-8 -*-
"""The Samsung Janitoo helper

"""

__license__ = """
    This file is part of Janitoo.

    Janitoo is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Janitoo is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Janitoo. If not, see <http://www.gnu.org/licenses/>.

"""
__author__ = 'Sébastien GALLET aka bibi21000'
__email__ = 'bibi21000@gmail.com'
__copyright__ = "Copyright © 2013-2014-2015-2016 Sébastien GALLET aka bibi21000"

import logging
logger = logging.getLogger(__name__)
import os, sys
import threading
import time
from datetime import datetime, timedelta

import sensors as pysensors

from janitoo.options import get_option_autostart
from janitoo.utils import HADD, HADD_SEP, json_dumps, json_loads
from janitoo.node import JNTNode
from janitoo.value import JNTValue
from janitoo.component import JNTComponent
from janitoo.thread import JNTBusThread
from janitoo.bus import JNTBus
from janitoo.classes import COMMAND_DESC


##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_METER = 0x0032
COMMAND_CONFIGURATION = 0x0070

assert(COMMAND_DESC[COMMAND_METER] == 'COMMAND_METER')
assert(COMMAND_DESC[COMMAND_CONFIGURATION] == 'COMMAND_CONFIGURATION')
##############################################################

def make_lmsensor(**kwargs):
    return LmSensor(**kwargs)

class LmSensor(JNTComponent):
    """ Use lmsensor to retrieve sensors. """

    def __init__(self, bus=None, addr=None, **kwargs):
        JNTComponent.__init__(self, 'hostsensor.lmsensor', bus=bus, addr=addr, name="LmSensor sensors",
                product_name="LmSensor", product_type="Software", product_manufacturer="LmSensor", **kwargs)
        self._lock =  threading.Lock()
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
        self._lmsensor_last = False
        self._lmsensor_next_run = datetime.now() + timedelta(seconds=15)

        uuid="config_filename"
        self.values[uuid] = self.value_factory['config_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The full path/name of config file to use',
            label='File',
            default='/etc/sensors3.conf',
        )

        uuid="temperature"
        self.values[uuid] = self.value_factory['sensor_temperature'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The temperatures from lm-sensors',
            label='Temperature',
            get_data_cb=self.get_temperature,
        )
        config_value = self.values[uuid].create_config_value(help='The name of the lmsensor', label='sensor_name', type=0x08)
        self.values[config_value.uuid] = config_value
        poll_value = self.values[uuid].create_poll_value(default=90)
        self.values[poll_value.uuid] = poll_value

        uuid="voltage"
        self.values[uuid] = self.value_factory['sensor_voltage'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The voltage from lm-sensors',
            label='Voltage',
            get_data_cb=self.get_volt,
        )
        config_value = self.values[uuid].create_config_value(help='The name of the lmsensor', label='sensor_name', type=0x08)
        self.values[config_value.uuid] = config_value
        poll_value = self.values[uuid].create_poll_value(default=90)
        self.values[poll_value.uuid] = poll_value

    def get_temperature(self, node_uuid, index):
        self.get_lmsensor()
        if self._lmsensor_last == True:
            return self.values["temperature"].get_data_index(node_uuid=node_uuid, index=index)

    def get_volt(self, node_uuid, index):
        self.get_lmsensor()
        if self._lmsensor_last == True:
            return self.values["voltage"].get_data_index(node_uuid=node_uuid, index=index)

    def check_heartbeat(self):
        """Check that the component is 'available'

        """
        #~ print "it's me %s : %s" % (self.values['upsname'].data, self._ups_stats_last)
        return self._lmsensor_last

    def get_lmsensor(self):
        """
        """
        if self._lmsensor_next_run < datetime.now():
            locked = self._lock.acquire(False)
            if locked == True:
                try:
                    _lmsensor = {}
                    pysensors.init(config_filename=self.values["config_filename"].data)
                    try:
                        for chip in pysensors.iter_detected_chips():
                            _lmsensor['%s'%chip] = {}
                            for feature in chip:
                                _lmsensor['%s'%chip][feature.label] = feature.get_value()
                    except:
                        logger.exception("[%s] - Exception in get_lmsensor", self.__class__.__name__)
                    finally:
                        pysensors.cleanup()
                    for val_id in ['temperature', 'voltage']:
                        for config in self.values[val_id].get_index_configs():
                            for chip in _lmsensor:
                                if config in _lmsensor[chip] :
                                    self.values[val_id].set_data_index(config=config, data=_lmsensor[chip][config])
                    self._lmsensor_last = True
                except:
                    logger.exception("[%s] - Exception in get_lmsensor", self.__class__.__name__)
                    self._lmsensor_last = False
                finally:
                    self._lock.release()
                    min_poll=99999
                    for val_id in ['temperature_poll', 'voltage_poll']:
                        if self.values[val_id].data > 0:
                            min_poll=min(min_poll, self.values[val_id].data)
                    self._lmsensor_next_run = datetime.now() + timedelta(seconds=min_poll)
