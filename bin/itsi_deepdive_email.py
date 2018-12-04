# Copyright (C) 2005-2018 Splunk Inc. All Rights Reserved.

import sys
import json
import platform
import subprocess
import itsi_deepdive_email_utils
import itsi_deepdive_email_config as cfg
import urllib2
import re

from splunk.clilib.bundle_paths import make_splunkhome_path

sys.path.append(make_splunkhome_path(['etc', 'apps', 'SA-ITOA', 'lib']))

from ITOA.fix_appserver_import import FixAppserverImports
from ITOA.setup_logging import setup_logging
from itsi.event_management.sdk.eventing import Event
from itsi.event_management.sdk.custom_event_action_base import CustomEventActionBase

class Email(CustomEventActionBase):

    HOST = cfg.splunk['public_host']
    PORT = cfg.splunk['port']

    CONTRIBUTING_KPI = 0
    AFFECTED_SERVICES = 1

    def __init__(self, settings):
        # initialize CustomEventActionBase
        self.logger = setup_logging("itsi_event_management.log", "itsi.event_action.emailalert")
        super(Email, self).__init__(settings, self.logger)

    def get_email_body(self, urls):
        return 'Hi Splunker,\n\n'\
              'You are receiving notable events review summary.\n\n'\
              '\t- Contributing KPIs: {0}\n\n'\
              '\t- Possible Affected Services: {1}\n\n'\
              .format(urls[self.CONTRIBUTING_KPI], urls[self.AFFECTED_SERVICES])

    def get_email_recipient(self, config):
        recipient = config.get('to')
        if recipient is None or not '@' in recipient:
            message = "Invalid Email Recipient"
            self.logger.error(message)
            raise Exception(message)

        return recipient.split(",") if "," in recipient else list(recipient)


    def get_formatted_data(self, lst_data, deepdive_id):
        set_data = set(lst_data)
        res = "("
        for kpiid in set_data:
            if deepdive_id == self.AFFECTED_SERVICES:
                res += 'kpiid="SHKPI-{0}"|'.format(kpiid)
                continue
            res += 'kpiid="{0}"|'.format(kpiid)

        res = res[:-1] + ")"
        return res.replace("|"," OR ")


    def get_link(self, lst_kpi):
        # Retrieving data
        laneSettingsCollection = json.dumps(itsi_deepdive_email_utils.getEntities(lst_kpi))\
                                     .replace(": ",":")\
                                     .replace(", ", ",")
        # Building up the link
        encoded_query = "laneSettingsCollection={0}&earliest=-60m&latest=now&owner=".format(urllib2.quote(laneSettingsCollection, safe=''))
        return "http://{0}:{1}/en-US/app/itsi/deep_dive?{2}".format(self.HOST, self.PORT, encoded_query)

    def execute(self):
        """
        Execute in bulk. For each event in the results file:
        1. extract the kpis from the event
        2. build URL and mail body
        3. get email details
        4. send emails

        Apart from the above, this method does nothing else.
        The rest is left to your implementation and imagination.
        """
        self.logger.debug('Received settings from splunkd=`%s`',json.dumps(self.settings))
        count = 0

        try:
            services = []
            kpis = []
            deepdive_urls = {}

            for data in self.get_event():
                if isinstance(data, Exception):
                    # Generator can yield an Exception
                    # We cannot print the call stack here reliably, because
                    # of how this code handles it, we may have generated an exception elsewhere
                    # Better to present this as an error
                    self.logger.error(data)
                    raise data

                if not data.get('event_id'):
                    self.logger.warning('Event does not have an `event_id`. No-op.')
                    continue

                event_id = data.get('event_id')
                service_ids = data.get('service_ids')

                if data.get('scoretype') == 'compositekpi_health':
                    kpiid = data.get('all_service_kpi_ids')
                    # self.logger.debug("Got kpiid: {0}".format(kpiid))
                    lst_kpi = re.findall(':(.+?)(?=\s|$)', kpiid)

                if service_ids and len(service_ids) > 0:
                    # self.logger.debug("Got service ids: {0}".format(service_ids))
                    if not service_ids in services:
                        services.append(service_ids)

                count += 1

            # All events parsed. Get links.
            lst_kpi = self.get_formatted_data(kpis, self.CONTRIBUTING_KPI)
            # self.logger.debug("Formatted kpis {0}".format(lst_kpi))
            deepdive_urls[self.CONTRIBUTING_KPI] = self.get_link(lst_kpi)

            lst_services = self.get_formatted_data(services, self.AFFECTED_SERVICES)
            # self.logger.debug("Formatted services {0}".format(lst_services))
            deepdive_urls[self.AFFECTED_SERVICES] = self.get_link(lst_services)

            self.logger.info("Ready to proceed with obtained URLs : {0}".format(deepdive_urls))

            # Links created. Finalising email configuration.
            config = self.get_config()
            config['to'] = ",".join(self.get_email_recipient(config))
            config['msg'] = self.get_email_body(deepdive_urls)

            # Send email.
            res, res_msg = itsi_deepdive_email_utils.send_email(config)
            if not res:
                raise Exception(res_msg)
            self.logger.info(res_msg)

        except ValueError, e:
            pass # best case, try every event.
        except Exception, e:
            self.logger.error('Failed to execute operations.')
            self.logger.exception(e)
            sys.exit(1)
        self.logger.info('Executed action. Processed events count=`{0}`.'.format(count))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--execute':
        input_params = sys.stdin.read()
        email = Email(input_params)
        email.execute()
