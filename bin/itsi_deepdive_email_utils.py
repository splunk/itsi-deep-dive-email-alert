# Copyright (C) 2005-2018 Splunk Inc. All Rights Reserved.

import sys
import itsi_deepdive_email_config as cfg

HOST = "localhost"
PORT = int(cfg.splunk['mgmt_port'])
USERNAME = cfg.splunk['username']
PASSWORD = cfg.splunk['password']

def connect():
    import splunklib.client as client

    # Create a Service instance and log in
    return client.connect(
        host=HOST,
        port=PORT,
        username=USERNAME,
        password=PASSWORD
        )

def getEntities(kpiid):
        import splunklib.results as results

        res = []
        kwargs_oneshot = {}
        searchquery_oneshot = "search index=itsi_summary {0}|dedup kpiid\
                                | lookup service_kpi_lookup _key AS itsi_service_id OUTPUT title AS subtitle\
                                | eval title = kpi | eval kpiServiceId = itsi_service_id | eval kpiId = kpiid\
                                | table title subtitle kpiId kpiServiceId".format(kpiid)

        oneshotsearch_results = connect().jobs.oneshot(searchquery_oneshot, **kwargs_oneshot)

        # Get the results and display them using the ResultsReader
        reader = results.ResultsReader(oneshotsearch_results)
        for item in reader:
            # Adding parameters
            item["laneType"] = "kpi"
            item["searchSource"] = "kpi"
            item["thresholdIndicationEnabled"] = "enabled"
            item["thresholdIndicationType"] = "stateIndication"

            res.append(item)
	return res

def send_email(data):
    import splunklib.results as results

    kwargs_oneshot = {}
    searchquery_oneshot = 'search makeresults | sendemail content_type=html to="{0}" subject="{1}" message="{2}"'\
                            .format(data.get('to'), data.get('subject','No subject'), data.get('msg',''))

    oneshotsearch_results = connect().jobs.oneshot(searchquery_oneshot, **kwargs_oneshot)

    try:
        results.ResultsReader(oneshotsearch_results)
        return (True, "Email sent")
    except Exception as e:
        return (False, e)
