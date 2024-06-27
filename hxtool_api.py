#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import random
import csv
from io import BytesIO
from io import StringIO
from collections import deque, defaultdict
import zipfile

try:
	from flask import Flask, request, Response, session, redirect, render_template, send_file, g, url_for, abort, Blueprint, current_app as app
except ImportError:
	print("hxtool requires the 'Flask' module, please install it.")
	exit(1)

import hxtool_logging
from hxtool_vars import HXTOOL_API_VERSION, default_encoding
from hx_lib import *
from hxtool_util import *
from hxtool_data_models import *
from hxtool_scheduler import *
from hxtool_scheduler_task import *
from hxtool_task_modules import *
from hx_openioc import openioc_to_hxioc

ht_api = Blueprint('ht_api', __name__, template_folder='templates')
logger = hxtool_logging.getLogger(__name__)

###################################
# Common User interface endpoints #
###################################

@ht_api.route('/api/v{0}/hostsets/list'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hostsets_list(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restListHostsets()
	if ret:
		response_data['data']['entries'].append({
			"_id": 9,
			"name": "All hosts",
			"type": "hidden",
			"url": "/hx/api/v3/host_sets/9"
			})
		(r, rcode) = create_api_response(ret, response_code, response_data)
		return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/getHealth'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def getHealth(hx_api_object):
	myHealth = {}
	(ret, response_code, response_data) = hx_api_object.restGetControllerVersion()
	if ret:
		myHealth['status'] = "OK"
		myHealth['version'] = response_data['data']
		return(app.response_class(response=json.dumps(myHealth), status=200, mimetype='application/json'))
	else:
		myHealth['status'] = "FAIL"
		return(app.response_class(response=json.dumps(myHealth), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/version/get'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_version_get(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetControllerVersion()
	(r, rcode) = create_api_response(ret, response_code, response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

#################
# Audit Manager #
#################
@ht_api.route('/api/v{0}/auditmanager/getaudits'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_auditmanager_getaudits(hx_api_object):
	r = hxtool_global.hxtool_db.auditGetCollections()

	# Grab all bulk acqs so we can use their data to enrich the table
	bulk_acqs = {}
	(ret, response_code, response_data) = hx_api_object.restListBulkAcquisitions()
	if ret:
		for entry in response_data['data']['entries']:
			bulk_acqs[entry['_id']] = entry

		response = {}
		mydata = []

		for res in r:
			row = {}
			res_data = eval(res['_id'])
			for key, value in res_data.items():
				row[key] = value
			row['count'] = res['count']
			row['action'] = res_data['bulk_acquisition_id']

			if res_data['bulk_acquisition_id'] in bulk_acqs.keys():
				row['created'] = bulk_acqs[res_data['bulk_acquisition_id']]['create_time'] 
				row['state'] = bulk_acqs[res_data['bulk_acquisition_id']]['state'] 
				row['name'] = bulk_acqs[res_data['bulk_acquisition_id']]['comment']
				row['hostset'] = bulk_acqs[res_data['bulk_acquisition_id']]['host_set']['name']
			else:
				row['created'] = ""
				row['state'] = ""
				row['name'] = ""
				row['hostset'] = ""

			mydata.append(row)

		response['columns'] = []
		for column in list(set().union(*(d.keys() for d in mydata))):
			response['columns'].append({ "data": column, "title": column })

		response['data'] = mydata

		return(app.response_class(response=json.dumps(response), status=200, mimetype='application/json'))
	else:
		return(app.response_class(response=json.dumps("Unable to list bulk acquisitions"), status=404, mimetype='application/json'))

@ht_api.route('/api/v{0}/auditmanager/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_auditmanager_remove(hx_api_object):
	rcode = 200
	rmessage = "Audit action remove"
	try:
		r = hxtool_global.hxtool_db.auditRemove(request.args.get('id'))
	except:
		rcode = 404
		rmessage = "Audit action remove failed"

	return(app.response_class(response=json.dumps(rmessage), status=rcode, mimetype='application/json'))

#################
# Audit viewer  #
#################
@ht_api.route('/api/v{0}/auditviewer/query'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_auditviewer_query(hx_api_object):

	mstr = hxtool_global.hxtool_db.queryParse(request.args.get('q'))
	
	if mstr['type'] == "find":
		try:
			if 'sort' in mstr.keys():
				r = hxtool_global.hxtool_db.auditQuery(mstr['query'], mstr['sort'])
			else:
				r = hxtool_global.hxtool_db.auditQuery(mstr['query'])
		except:
			return(app.response_class(response=json.dumps(r), status=404, mimetype='application/json'))

		response = {}
		mydata = []
		for res in r:
			row = {
				"hostname": res['hostname'],
				"generator": res['generator'],
				"hx_host": res['hx_host'],
				"bulk_acquisition_id": res['bulk_acquisition_id']
			}
			for key in res[res['generator_item_name']].keys():
				row[res['generator_item_name'] + "/" + key] = res[res['generator_item_name']][key]
			mydata.append(row)
		
		response['columns'] = []
		for column in list(set().union(*(d.keys() for d in mydata))):
			response['columns'].append({ "data": column, "title": column })

		mynewdata = []
		for myrecord in mydata:
			for mykey in list(set().union(*(d.keys() for d in mydata))):
				if mykey not in myrecord.keys():
					myrecord[mykey] = ""
			mynewdata.append(myrecord)

		response['data'] = mynewdata

	if mstr['type'] == "aggregate":
		try:
			r = hxtool_global.hxtool_db.auditQueryAggregate(mstr['query'])
		except:
			return(app.response_class(response=json.dumps(r), status=404, mimetype='application/json'))

		response = {}
		mydata = []

		for res in r:
			row = {}
			res_data = eval(res['_id'])
			for key, value in res_data.items():
				row[key] = value
			row['count'] = res['count']
			mydata.append(row)

		response['columns'] = []
		for column in list(set().union(*(d.keys() for d in mydata))):
			response['columns'].append({ "data": column, "title": column })

		response['data'] = mydata

	return(app.response_class(response=json.dumps(response), status=200, mimetype='application/json'))

################
# Acquisitions #
################
@ht_api.route('/api/v{0}/acquisition/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restDeleteFile(request.args.get('url'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="acquisition", action="remove", host=request.args.get('url'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))


@ht_api.route('/api/v{0}/acquisition/get'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_get(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetUrl(request.args.get('url'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/download'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_download(hx_api_object):
	if request.args.get('id'):
		if request.args.get('content') == "json":
			(ret, response_code, response_data) = hx_api_object.restDownloadFile(request.args.get('id'), accept = "application/json")
		else:
			(ret, response_code, response_data) = hx_api_object.restDownloadFile(request.args.get('id'))
		if ret:
			flask_response = Response(iter_chunk(response_data))
			flask_response.headers['Content-Type'] = response_data.headers['Content-Type']
			flask_response.headers['Content-Disposition'] = response_data.headers['Content-Disposition']
			app.logger.info(format_activity_log(msg="acquisition", action="download", host=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
			return flask_response
		else:
			(r, rcode) = create_api_response(ret, response_code, response_data)
			return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))
	else:
		abort(404)

@ht_api.route('/api/v{0}/acquisition/new'.format(HXTOOL_API_VERSION), methods=['GET', 'POST'])
@valid_session_required
def hxtool_api_acquisition_new(hx_api_object):

	if request.method == 'POST':
		fc = request.files['script']
		myscript = fc.read()
		myAgentID = request.form.get('id')
		myScriptName = request.form.get('scriptname')
		do_skip_base64 = False
	elif request.method == 'GET':
		myscript = hxtool_global.hxtool_db.scriptGet(request.args.get('scriptid'))['script']
		do_skip_base64 = True
		myAgentID = request.args.get('id')
		myScriptName = request.args.get('scriptname')

	(ret, response_code, response_data) = hx_api_object.restNewAcquisition(myAgentID, myScriptName, myscript, skip_base64=do_skip_base64)
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="acquisition", action="new", host=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/file'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_file(hx_api_object):

	if request.args.get('type') == "api":
		mode = True
	if request.args.get('type') == "raw":
		mode = False

	if 'filepath' in request.args:
		if '\\' in request.args.get('filepath'):
			fileName = request.args.get('filepath').rsplit("\\", 1)[1]
			filePath = request.args.get('filepath').rsplit("\\", 1)[0]
		elif '/' in request.args.get('filepath'):
			fileName = request.args.get('filepath').rsplit("/", 1)[1]
			filePath = request.args.get('filepath').rsplit("/", 1)[0]
	elif 'path' in request.args:
		filePath = request.args.get('path')
		fileName = request.args.get('filename')
		
	(ret, response_code, response_data) = hx_api_object.restAcquireFile(request.args.get('id'), filePath, fileName, mode)

	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="file acquisition", action="new", host=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/triage'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_triage(hx_api_object):

	if request.args.get('type') == "standard":
		(ret, response_code, response_data) = hx_api_object.restAcquireTriage(request.args.get('id'))
	elif request.args.get('type') in ["1", "2", "4", "8"]:
		mytime = datetime.datetime.now() - datetime.timedelta(hours = int(request.args.get('type')))
		(ret, response_code, response_data) = hx_api_object.restAcquireTriage(request.args.get('id'), mytime.strftime('%Y-%m-%d %H:%M:%S'))
	elif request.args.get('type') == "timestamp":
		(ret, response_code, response_data) = hx_api_object.restAcquireTriage(request.args.get('id'), request.args.get('timestamp'))

	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="triage acquisition", action="new", host=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

#####################
# Enterprise Search #
#####################
# Stop
@ht_api.route('/api/v{0}/enterprise_search/stop'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_enterprise_search_stop(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restCancelJob('searches', request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="enterprise search", action="stop", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

# Remove
@ht_api.route('/api/v{0}/enterprise_search/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_enterprise_search_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restDeleteJob('searches', request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="enterprise search", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

# New search from openioc store
@ht_api.route('/api/v{0}/enterprise_search/new/db'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_enterprise_search_new_db(hx_api_object):
	
	if 'sweephostset' not in request.args or request.args['sweephostset'] == "false":
		return(app.response_class(response=json.dumps("Please select a host set."), status=400, mimetype='application/json'))

	ioc_script = hxtool_global.hxtool_db.oiocGet(request.args.get('ioc'))

	ignore_unsupported_items = True
	if 'esskipterms' in request.args.keys():
		if request.args.get('esskipterms') == "false":
			ignore_unsupported_items = False
		else:
			ignore_unsupported_items = True

	mydisplayname = "N/A"
	if 'displayname' in request.args.keys():
		mydisplayname = request.args.get("displayname")

	(start_time, schedule) = parse_schedule(request.args)
	
	enterprise_search_task = hxtool_scheduler_task(session['ht_profileid'], "Enterprise Search Task", start_time = start_time)
	
	if schedule:
		enterprise_search_task.set_schedule(**schedule)

	# IOC conditions can be in "event only" or "eventItem" format. The IOC content shipped via DTI
	# and available in the Endpoint Supplementary IOCs on the Market use the "event only" format.
	# Other IOCs may be in "eventItem" format, depending on how they are created using OpenIOC
	# editor. Most importantly, the HX Enterprise Search API expects "eventItem" format. This
	# regex adds the necessary "eventItem" prefix to any IOC conditions in "event only" format.
	# For example, this regex converts:
	#   <Context document="processEvent" search="processEvent/process" type="event" />
	# to:
	#   <Context document="eventItem" search="eventItem/processEvent/process" type="event" />
    # This will not convert conditions such as:
	#   <Context document="FileItem" search="FileItem/FullPath" type="endpoint" />

	event_item_script = re.sub(
	    '<Context\s+document="(?!eventItem).+"\s+search="(?!eventItem/)(?P<search>.+Event.+)"\s+type="(?!mir).+"\s+/>',
	    '<Context document="eventItem" search="eventItem/\g<search>" type="event" />',
	    HXAPI.b64(ioc_script['ioc'], True).decode('utf-8'),
	    flags=re.IGNORECASE)

	enterprise_search_task.add_step(enterprise_search_task_module, kwargs = {
										'script' : HXAPI.b64(event_item_script),
										'hostset_id' : request.args.get('sweephostset'),
										'ignore_unsupported_items' : ignore_unsupported_items,
										'skip_base64': True,
										'displayname': mydisplayname
									})
	hxtool_global.hxtool_scheduler.add(enterprise_search_task)

	app.logger.info(format_activity_log(msg="enterprise search", action="new", user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

# New search from file
@ht_api.route('/api/v{0}/enterprise_search/new/file'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_enterprise_search_new_file(hx_api_object):
	
	if 'sweephostset' not in request.form or request.form['sweephostset'] == "false":
		return(app.response_class(response=json.dumps("Please select a host set."), status=400, mimetype='application/json'))
		
	fc = request.files['ioc']
	ioc_script = fc.read()

	ignore_unsupported_items = True
	if 'esskipterms' in request.form.keys():
		if request.form.get('esskipterms') == "false":
			ignore_unsupported_items = False
		else:
			ignore_unsupported_items = True

	mydisplayname = "N/A"
	if 'displayname' in request.form.keys():
		mydisplayname = request.form.get("displayname")

	(start_time, schedule) = parse_schedule(request.form)	

	enterprise_search_task = hxtool_scheduler_task(session['ht_profileid'], "Enterprise Search Task", start_time = start_time)
	
	if schedule:
		enterprise_search_task.set_schedule(**schedule)

	# see comment in hxtool_api_enterprise_search_new_db above
	event_item_script = re.sub(
		'<Context\s+document="(?!eventItem).+"\s+search="(?!eventItem/)(?P<search>.+Event.+)"\s+type="(?!mir).+"\s+/>',
		'<Context document="eventItem" search="eventItem/\g<search>" type="event" />',
		ioc_script.decode('utf-8'),
		flags=re.IGNORECASE)

	enterprise_search_task.add_step(enterprise_search_task_module, kwargs = {
										'script' : HXAPI.b64(event_item_script),
										'hostset_id' : request.form.get('sweephostset'),
										'ignore_unsupported_items' : ignore_unsupported_items,
										'skip_base64': True,
										'displayname': mydisplayname
									})
	hxtool_global.hxtool_scheduler.add(enterprise_search_task)

	app.logger.info(format_activity_log(msg="enterprise search", action="new", user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

#########
# Hosts #
#########
@ht_api.route('/api/v{0}/hosts/config'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hosts_config(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetUrl("/hx/api/v3/hosts/" + request.args.get('id') + "/configuration/actual.json")
	(r, rcode) = create_api_response(response_data = response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/hosts/get'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hosts_get(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetHostSummary(request.args.get('id'))
	(r, rcode) = create_api_response(response_data = response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/hosts/sysinfo'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hosts_sysinfo(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetHostSysinfo(request.args.get('id'))
	(r, rcode) = create_api_response(response_data = response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/hosts/contain'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hosts_contain(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restRequestContainment(request.args.get('id'))
	(r, rcode) = create_api_response(response_data = response_data)
	app.logger.info(format_activity_log(msg="host action", action="containment request", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/hosts/uncontain'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hosts_uncontain(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restRemoveContainment(request.args.get('id'))
	(r, rcode) = create_api_response(response_data = response_data)
	app.logger.info(format_activity_log(msg="host action", action="uncontain", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/hosts/contain/approve'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hosts_contain_approve(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restApproveContainment(request.args.get('id'))
	(r, rcode) = create_api_response(response_data = response_data)
	app.logger.info(format_activity_log(msg="host action", action="containment approval", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/hosts/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_hosts_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restDeleteHostByID(request.args.get('id'))
	(r, rcode) = create_api_response(response_data = response_data)	
	app.logger.info(format_activity_log(msg="host action", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

###################
# Manage OpenIOCs #
###################
@ht_api.route('/api/v{0}/openioc/view'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_openioc_view(hx_api_object):
	storedioc = hxtool_global.hxtool_db.oiocGet(request.args.get('id'))
	(r, rcode) = create_api_response(response_data = json.dumps(storedioc))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/openioc/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_openioc_remove(hx_api_object):
	hxtool_global.hxtool_db.oiocDelete(request.args.get('id'))
	(r, rcode) = create_api_response()
	app.logger.info(format_activity_log(msg="openioc action", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/openioc/upload'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_openioc_upload(hx_api_object):

	fc = request.files['myioc']
	rawioc = fc.read()
	hxtool_global.hxtool_db.oiocCreate(request.form['iocname'], HXAPI.b64(rawioc), session['ht_user'])
	(r, rcode) = create_api_response(ret=True)
	app.logger.info(format_activity_log(msg="openioc action", action="new", name=request.form['iocname'], user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/openioc/download'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_openioc_download(hx_api_object):

	myiocData = hxtool_global.hxtool_db.oiocGet(request.args.get('id'))

	buffer = BytesIO()
	buffer.write(json.dumps(HXAPI.b64(myiocData['ioc'], decode=True, decode_string=True)).encode(default_encoding))
	buffer.seek(0)

	app.logger.info(format_activity_log(msg="openioc action", action="download", name=myiocData['iocname'], user=session['ht_user'], controller=session['hx_ip']))
	return send_file(buffer, download_name=myiocData['iocname'] + ".ioc", as_attachment=True)

##########
# Alerts #
##########
@ht_api.route('/api/v{0}/alerts/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_alerts_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restDeleteJob('alerts', request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="alert action", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/alerts/get'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_alerts_get(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetAlertID(request.args.get('id'))
	# Workaround for matching condition which isn't a part of the response
	if response_data.get('data', None) is not None and response_data['data']['source'] == "IOC":
		# Handle missing indicator object when multiple IOCs hit. ENDPT-52003
		if response_data['data'].get('indicator', None) is None:
			(cret, cresponse_code, cresponse_data) = hx_api_object.restGetIndicatorFromCondition(response_data['data']['condition']['_id'])
			if cret and len(cresponse_data['data']['entries']) > 0:
				tlist = [ _['name'] for _ in cresponse_data['data']['entries'] ]
				response_data['data'].update({
					'indicator' : { 
						'display_name' : "; ".join(tlist) 
				}})
		(cret, cresponse_code, cresponse_data) = hx_api_object.restGetConditionDetails(response_data['data']['condition']['_id'])
		if ret:
			response_data['data']['condition']['tests'] = cresponse_data['data']['tests']
			(r, rcode) = create_api_response(ret, response_code, response_data)
			return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))
	else:
		(r, rcode) = create_api_response(ret, response_code, response_data)
		return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))			

#####################
# Alert Annotations #
#####################
@ht_api.route('/api/v{0}/annotation/add'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_annotation_add(hx_api_object):
	hxtool_global.hxtool_db.alertCreate(session['ht_profileid'], request.form['id'])
	hxtool_global.hxtool_db.alertAddAnnotation(session['ht_profileid'], request.form['id'], request.form['text'], request.form['state'], session['ht_user'])
	app.logger.info(format_activity_log(msg="annotation action", action="new", id=request.form['id'], user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))


@ht_api.route('/api/v{0}/annotation/alert/view'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_annotation_alert_view(hx_api_object):
	alertAnnotations = hxtool_global.hxtool_db.alertGet(session['ht_profileid'], request.args.get('id'))
	return(app.response_class(response=json.dumps(alertAnnotations), status=200, mimetype='application/json'))

#############
# Scheduler #
#############
@ht_api.route('/api/v{0}/scheduler/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_scheduler_remove(hx_api_object):
	key_to_delete = request.args.get('id')

	hxtool_global.hxtool_scheduler.remove(key_to_delete, delete_children=True)

	app.logger.info(format_activity_log(msg="scheduler action", action="remove", id=key_to_delete, user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/scheduler_health'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def scheduler_health(hx_api_object):
	return(app.response_class(response=json.dumps(hxtool_global.hxtool_scheduler.status()), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/scheduler_tasks'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def scheduler_tasks(hx_api_object):
	mytasks = {}
	mytasks['data'] = []
	for task in hxtool_global.hxtool_scheduler.tasks():
		if not task['parent_id']:

			taskstates = {}
			for subtask in hxtool_global.hxtool_scheduler.tasks():
				if subtask['parent_id'] == task['task_id']:
					if not task_states.description.get(subtask['state'], "Unknown") in taskstates.keys():
						taskstates[task_states.description.get(subtask['state'], "Unknown")] = 1
					else:
						taskstates[task_states.description.get(subtask['state'], "Unknown")] += 1

			mytasks['data'].append({
				"DT_RowId": task['task_id'],
				"profile": task['profile_id'],
				"profile_name": task['profile_name'],
				"child_states": json.dumps(taskstates),
				"name": task['name'],
				"enabled": task['enabled'],
				"last_run": str(task['last_run']),
				"next_run": str(task['next_run']),
				"immutable": task['immutable'],
				"state": task_states.description.get(task['state'], "Unknown"),
				"action": task['task_id']
				})
	return(app.response_class(response=json.dumps(mytasks), status=200, mimetype='application/json'))

################
# Task profile #
################
@ht_api.route('/api/v{0}/taskprofile/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_taskprofile_remove(hx_api_object):
	hxtool_global.hxtool_db.taskProfileDelete(request.args.get('id'))
	(r, rcode) = create_api_response(ret=True)
	app.logger.info(format_activity_log(msg="task profile action", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/taskprofile/new'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_taskprofile_new(hx_api_object):
	mydata = request.get_json(silent=True)
	hxtool_global.hxtool_db.taskProfileAdd(mydata['name'], session['ht_user'], mydata['params'])
	(r, rcode) = create_api_response(ret=True)
	app.logger.info(format_activity_log(msg="task profile action", action="new", name=mydata['name'], user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

###############
# Host Groups #
###############
@ht_api.route('/api/v{0}/hostgroups'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_hostgroup_add(hx_api_object):
	hostgroup_data = request.json
	hxtool_global.hxtool_db.hostGroupAdd(session['profile_id'], hostgroup_data['name'], session['ht_user'], hostgroup_data['agent_ids'])
	(r, rcode) = create_api_response(ret=True)
	logger.info(format_activity_log(msg="host group action", action="new", name=hostgroup_data['name'], user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/hostgroups/<uuid:hostgroup_id>'.format(HXTOOL_API_VERSION), methods=['GET', 'DELETE'])
@valid_session_required
def hxtool_api_hostgroup_id(hx_api_object, hostgroup_id):
	hostgroup_id = str(hostgroup_id)
	if request.method == 'GET':
		hostgroup = hxtool_global.hxtool_db.hostGroupGet(hostgroup_id)
		if hostgroup:
			(r, rcode) = create_api_response(ret=True, response_code=200, response_data=hostgroup)
		else:
			(r, rcode) = create_api_response(ret=False, response_code=404)
		return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))
	elif request.method == 'DELETE':
		hxtool_global.hxtool_db.hostGroupRemove(hostgroup_id)
		(r, rcode) = create_api_response(ret=True)
		logger.info(format_activity_log(msg="host group action", action="remove", hostgroup_id=hostgroup_id, user=session['ht_user'], controller=session['hx_ip']))
		return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

####################
# Bulk Acquisition #
####################
# Remove
@ht_api.route('/api/v{0}/acquisition/bulk/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_bulk_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restDeleteJob('acqs/bulk', request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="bulk acquisition action", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

# Stop
@ht_api.route('/api/v{0}/acquisition/bulk/stop'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_bulk_stop(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restCancelJob('acqs/bulk', request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="bulk acquisition action", action="stop", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

# Stop download
@ht_api.route('/api/v{0}/acquisition/bulk/stopdownload'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_bulk_stopdownload(hx_api_object):
	ret = hxtool_global.hxtool_db.bulkDownloadUpdate(request.args.get('id'), stopped = True)
	app.logger.info(format_activity_log(msg="bulk acquisition action", action="stop download", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

# Download
@ht_api.route('/api/v{0}/acquisition/bulk/download'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_bulk_download(hx_api_object):
	hostset_id = -1
	(ret, response_code, response_data) = hx_api_object.restGetBulkDetails(request.args.get('id'))
	if ret:
		if 'host_set' in response_data['data']:
			hostset_id = int(response_data['data']['host_set']['_id'])
	
	(ret, response_code, response_data) = hx_api_object.restListBulkHosts(request.args.get('id'))
	
	if ret and response_data and len(response_data['data']['entries']) > 0:
		bulk_download_eid = hxtool_global.hxtool_db.bulkDownloadCreate(session['ht_profileid'], hostset_id = hostset_id, task_profile = None)
		
		bulk_acquisition_hosts = {}
		task_list = []
		for host in response_data['data']['entries']:
			bulk_acquisition_hosts[host['host']['_id']] = {'downloaded' : False, 'hostname' :  host['host']['hostname']}
			bulk_acquisition_download_task = hxtool_scheduler_task(session['ht_profileid'], 'Bulk Acquisition Download: {}'.format(host['host']['hostname']))
			bulk_acquisition_download_task.add_step(bulk_download_task_module, kwargs = {
														'bulk_download_eid' : bulk_download_eid,
														'agent_id' : host['host']['_id'],
														'host_name' : host['host']['hostname']
													})
			# This works around a nasty race condition where the task would start before the download job was added to the database				
			task_list.append(bulk_acquisition_download_task)
		
		hxtool_global.hxtool_db.bulkDownloadUpdate(bulk_download_eid, hosts = bulk_acquisition_hosts, bulk_acquisition_id = int(request.args.get('id')))
	
		hxtool_global.hxtool_scheduler.add_list(task_list)

		app.logger.info(format_activity_log(msg="bulk acquisition action", action="download", id=request.args.get('id'), hostset=hostset_id, user=session['ht_user'], controller=session['hx_ip']))
	else:
		app.logger.warn(format_activity_log(msg="bulk acquisition action", action="download", error="No host entries were returned for bulk acquisition", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))

	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

# New bulk acquisiton from scriptstore
@ht_api.route('/api/v{0}/acquisition/bulk/new/db'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_bulk_new_db(hx_api_object):

	if 'bulkhostset' not in request.args or request.args['bulkhostset'] == "false":
		return(app.response_class(response=json.dumps("Please select a host set."), status=400, mimetype='application/json'))

	(start_time, schedule) = parse_schedule(request.args)
	
	should_download = False
	
	bulk_acquisition_script = hxtool_global.hxtool_db.scriptGet(request.args.get('bulkscript'))['script']
	skip_base64 = True
	
	task_profile = None
	if request.args.get('taskprocessor') != "false":
		task_profile = request.args.get('taskprocessor', None)
		should_download = True

	submit_bulk_job(bulk_acquisition_script, 
					hostset_id = int(request.args.get('bulkhostset')),
					start_time = start_time, 
					schedule = schedule, 
					task_profile = task_profile, 
					download = should_download,
					skip_base64 = skip_base64,
					comment=request.args.get('displayname'))
	app.logger.info(format_activity_log(msg="bulk acquisition action", action="new", user=session['ht_user'], controller=session['hx_ip']))
	
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

# New bulk acquisition from file
@ht_api.route('/api/v{0}/acquisition/bulk/new/file'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_acquisition_bulk_new_file(hx_api_object):

	if 'bulkhostset' not in request.form or request.form['bulkhostset'] == "false":
		return(app.response_class(response=json.dumps("Please select a host set."), status=400, mimetype='application/json'))

	(start_time, schedule) = parse_schedule(request.form)
	
	bulk_acquisition_script = None
	skip_base64 = False
	should_download = False
	
	f = request.files['bulkscript']
	bulk_acquisition_script = f.read()
	
	task_profile = None
	if request.form['taskprocessor'] != "false":
		task_profile = request.form.get('taskprocessor', None)
		should_download = True

	submit_bulk_job(HXAPI.compat_str(bulk_acquisition_script), 
					hostset_id = int(request.form['bulkhostset']),
					start_time = start_time, 
					schedule = schedule, 
					task_profile = task_profile, 
					download = should_download,
					skip_base64 = skip_base64,
					comment=request.form['displayname'])
	app.logger.info(format_activity_log(msg="bulk acquisition action", action="new", user=session['ht_user'], controller=session['hx_ip']))

	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

###########
# Scripts #
###########
@ht_api.route('/api/v{0}/scripts/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_scripts_remove(hx_api_object):
	hxtool_global.hxtool_db.scriptDelete(request.args.get('id'))
	(r, rcode) = create_api_response(ret=True)
	app.logger.info(format_activity_log(msg="script action", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/scripts/upload'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_scripts_upload(hx_api_object):

	fc = request.files['myscript']
	rawscript = fc.read()
	hxtool_global.hxtool_db.scriptCreate(request.form['scriptname'], HXAPI.b64(rawscript), session['ht_user'])
	(r, rcode) = create_api_response(ret=True)
	app.logger.info(format_activity_log(msg="script action", action="new", name=request.form['scriptname'], user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/scripts/builder'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_scripts_builder(hx_api_object):
	mydata = request.get_json(silent=True)

	hxtool_global.hxtool_db.scriptCreate(mydata['scriptName'], HXAPI.b64(json.dumps(mydata['script'], indent=4).encode()), session['ht_user'])
	app.logger.info(format_activity_log(msg="new scriptbuilder acquisiton script", name=mydata['scriptName'], user=session['ht_user'], controller=session['hx_ip']))

	(r, rcode) = create_api_response(ret=True)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/scripts/download'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_scripts_download(hx_api_object):

	myscriptData = hxtool_global.hxtool_db.scriptGet(request.args.get('id'))

	buffer = BytesIO()
	buffer.write(HXAPI.b64(myscriptData['script'], decode=True, decode_string=True).encode(default_encoding))
	buffer.seek(0)

	app.logger.info(format_activity_log(msg="script action", action="download", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return send_file(buffer, download_name=myscriptData['scriptname'] + ".json", as_attachment=True)

########################
# IOC Streaming API    #
########################
@ht_api.route('/api/v{0}/streaming_indicator_category/get_edit_policies'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_streaming_indicator_category_get_edit_policies(hx_api_object):
	# streaming indicators don't have categories, so make them up for our own purposes.  We just need one of each type.
	r = {
		'api_success':True,
		'api_response_code':200,
		'api_response': json.dumps({
			"1": "read_only", 
			"2": "full", 
			"3": "edit_delete", 
			"4": "delete"
			})
		}

	return(app.response_class(response=json.dumps(r), status=200, mimetype='application/json'))
	
@ht_api.route('/api/v{0}/datatable_streaming_indicators'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_streaming_indicators(hx_api_object):
	
	mydata = {}
	mydata['data'] = []

	mySort = 'updated_at:desc'	#sort most recent updates to the top
	myFilter = '{"operator":"eq","field":"deleted","arg":["false"]}'	# show only active indicators
	(ret, response_code, response_data) = hx_api_object.restListStreamingIndicators(sort_term=mySort, filter_term=myFilter)
	if ret:
		for indicator in response_data['data']['entries']:
			mydata['data'].append(indicator_dict_from_indicator(indicator=indicator, hx_api_object=hx_api_object))

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/streaming_indicators/get/conditions'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_streaming_indicators_get_conditions(hx_api_object):
	uuid = request.args.get('uuid')
	(ret, response_code, condition_class_conditions) = hx_api_object.restListConditionsForStreamingIndicator(indicator_id=uuid)

	myconditions = { "conditions": condition_class_conditions }

	(r, rcode) = create_api_response(ret, response_code, myconditions)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/streaming_indicators/enable'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_streaming_indicators_enable(hx_api_object):
	mydata = json.loads(request.form.get('data'))
	uuid = mydata['id']
	is_enabled = mydata['is_enabled']

	(ret, response_code, resp_data) = hx_api_object.restEnableStreamingIndicator(ioc_id=uuid, is_enabled=is_enabled)
	(r, rcode) = create_api_response(ret, response_code, resp_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/streaming_indicators/newOrUpdate'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_streaming_indicators_newOrUpdate(hx_api_object):

	mydata = json.loads(request.form.get('rule'))
	'''
	Keys within mydata:
		'name' 				- the name of the rule
		'description' 		- the description of the rule
		'platform' 			- the platform assigned to the rule, or 'all'
		'originalname' 		- the original name of the rule
		'originalcategory' 	- the original category of the rule
		'iocuri'			- the fully qualified uri of the rule, for example:'/hx/api/plugins/ioc-streaming/v1/indicators/e3d70699-4d46-4b3c-8a5b-8d46ef1e22a2'
							  The uri will be empty if this is a new rule.
		'xxx_condition'		- The condition to attach.  If there are more than one, they will appear in sequence.  A condition is not required
							  'xxx' will be the UUID of the condition.  If the condition is a new one, then 'xxx' with be 'undefined'

		Each condition is an array of Tests
		Keys with Tests:
			'case'		- boolean to make the comparison case sensitive
			'data'		- the data to test for within the comparison
			'field'		- the field for the comparions
			'group'		- the groupd for the field, for example:'fileWriteEvent'
			'negate'	- boolean to reverse the sense of the test
			'operator'	- the comparison operator
			'type'		- the data type of the field, for example:'text'
	'''
	
	mydata['category'] = ''	# no value, for now
	orig_uri = mydata.get('iocuri')  # if None this is a new indicator

	if mydata['platform'] == "all":
		chosenplatform = ['win', 'osx', 'linux']
	else:
		chosenplatform = [mydata['platform']]

	# Our approach is to simply create a new indicator with conditions (even if this is an update).  For an update, we will delete the old condition.
	# We do this so that we can roll-back to the original in the case that there is a problem with the update.

	# create the new indicator.  If this is an update, the orginal will be removed below.
	(ret, response_code, response_data) = hx_api_object.restAddStreamingIndicator(
															ioc_category=mydata['category'], 
															display_name=mydata['name'], 
															create_text=session['ht_user'], 
															platforms=chosenplatform, 
															description=mydata['description'])
	if ret:
		new_ioc_id = response_data['id']

		#create each condition for the new indicator
		for key, value in mydata.items():
			if "_condition" in key:
				(form_iocguid, ioctype) = key.split("_")
				mytests = {"tests": []}
				for test in value:	# value is an array of tests
					mytests['tests'].append({
						"token": 		 test['group'] + "/" + test['field'], 
						"operator": 	 test['operator'], 
						"type": 		 test['type'], 
						"value": 		 test['data'],
						"preservecase" : test['case'],
						"negate" : 		 test['negate']
					})

				(ret, response_code, response_data) = hx_api_object.restAddStreamingCondition(mydata['category'], new_ioc_id, ioctype, mytests)
				if not ret:
					# Remove the new indicator if condition push was unsuccessful.  Note that this will remove any conditions that were attached
					# ahead of this failure
					(ret, response_code, response_data) = hx_api_object.restDeleteStreamingIndicator(mydata['category'], new_ioc_id)
					return ('failed to create indicator conditions, check your conditions', 500)
		# All OK
		app.logger.info(format_activity_log(msg="rule action", action="new", name=mydata['name'], category=mydata['category'], user=session['ht_user'], controller=session['hx_ip']))
		if orig_uri:
			# Remove the original indicator and original conditions
			(ret, response_code, response_data) = hx_api_object.restDeleteStreamingIndicator(mydata['originalcategory'], orig_uri.split("/")[-1])
			if not ret:
				app.logger.warn(format_activity_log(msg="rule action", action="update", reason="failed to remove old indicator", user=session['ht_user'], controller=session['hx_ip']))
		return ('', 204)
	else:
		# Failed to create indicator
		app.logger.warn(format_activity_log(msg="rule action", action="new", reason="failed to create indicator", user=session['ht_user'], controller=session['hx_ip']))
		return ('failed to create indicator', 500)	

@ht_api.route('/api/v{0}/streaming_indicators/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_streaming_indicators_remove(hx_api_object):
	(ret, response_code, response_data) =  hx_api_object.restDeleteStreamingIndicator('', request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="rule action", action="remove", name=request.args.get('url'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

#serialize from an indicator response to a dictionary of properties
def indicator_dict_from_indicator(indicator, hx_api_object):
	return {
				"DT_RowId": 		indicator['id'],
				"url": 				hx_api_object.buildStreamingIndicatorURI(indicator_id=indicator['id']),
				"name" : 			indicator['name'],
				"description": 		indicator['description'],
				"last_updated": 	indicator['updated_at'],
				"category_id":		1 if(indicator['category'] == 'FireEye') else 2, # see hxtool_api_streaming_indicator_category_get_edit_policies() above
				"category_name": 	indicator['category'],
				"updated_by": 		indicator['updated_by'],
				"meta": 			indicator['meta'],
				"platforms":		streaming_indicator_platforms_supported(indicator),
				"is_enabled":		indicator['enabled']
			}

# return an array of platforms supported
def streaming_indicator_platforms_supported(indicator):
	platforms = []
	if indicator['supports_win']:
		platforms.append('win')
	if indicator['supports_linux']:
		platforms.append('linux')
	if indicator['supports_osx']:
		platforms.append('osx')
	return platforms

@ht_api.route('/api/v{0}/streaming_indicators/export'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_streaming_indicators_export(hx_api_object):
	iocList = request.json
	if(len(iocList)):
		for uuid, ioc in iocList.items():
			(ret, _, response_data) = hx_api_object.restListConditionsForStreamingIndicator(indicator_id=uuid)
			if ret:
				ioc['uri_name'] = uuid	# reduce the uri_name to simply the uuid (removing the path info)
				iocList[uuid]['conditions'] = []
				for item in response_data['data']['entries']:
					iocList[uuid]['conditions'].append(item['condition']['tests'])

		buffer = BytesIO()
		if len(iocList.keys()) == 1:
			iocfname = list(iocList.keys())[0] + ".ioc"
			buffer.write(json.dumps(iocList, indent=4, ensure_ascii=False).encode(default_encoding))
		else:
			iocfname = "multiple_indicators.zip"
			with zipfile.ZipFile(buffer, 'w') as zf:
				for uuid, ioc in iocList.items():
					zf.writestr(uuid + '.ioc', json.dumps({uuid:ioc}, indent=4, ensure_ascii=False).encode(default_encoding))
			zf.close()

		buffer.seek(0)
		
		app.logger.info(format_activity_log(msg="streaming rule action", action="export", name=iocfname, user=session['ht_user'], controller=session['hx_ip']))
		return send_file(buffer, download_name=iocfname, as_attachment=True)
	return('Nothing selected to export', 500)

@ht_api.route('/api/v{0}/streaming_indicators/import'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_streaming_indicators_import(hx_api_object):
	files = request.files.getlist('ruleImport')
	
	import_platform = request.form.get('platform', '')
	if import_platform == "all":
		import_platform = ['win', 'osx', 'linux']
	else:
		import_platform = [import_platform]
	
	for file in files:
		# we may have a zip file, or a list of one or more files
		if (zipfile.is_zipfile(file)):
			# we have a zip file
			with zipfile.ZipFile(file) as myzip:
				# list all the files in the zip
				zfiles = myzip.namelist()
				# for each zip file
				for zfile in zfiles:
					with myzip.open(zfile) as myfile:
						file_content = myfile.read().decode(default_encoding)
						try:
							iocs = json.loads(file_content)	
						except json.decoder.JSONDecodeError:
							iocs = openioc_to_hxioc(file_content, import_platform)
							if iocs is None:
								app.logger.warn(format_activity_log(msg="rule action fail", reason="{} is not a valid Endpoint Security (HX) JSON or OpenIOC 1.1 indicator." .format(file.filename), action="import", user=session['ht_user'], controller=session['hx_ip']))
								continue
								
						hxtool_handle_streaming_indicator_import(hx_api_object=hx_api_object, iocs=iocs)
		else:
			# not a zip file
			file.seek(0)  # rewind to the start of the file
			file_content = file.read().decode(default_encoding)
			try:
				iocs = json.loads(file_content)
			except json.decoder.JSONDecodeError:
				iocs = openioc_to_hxioc(file_content, import_platform)
				if iocs is None:
					app.logger.warn(format_activity_log(msg="rule action fail", reason="{} is not a valid Endpoint Security (HX) JSON or OpenIOC 1.1 indicator." .format(file.filename), action="import", user=session['ht_user'], controller=session['hx_ip']))
					continue
					
			hxtool_handle_streaming_indicator_import(hx_api_object=hx_api_object, iocs=iocs)
		
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

def hxtool_handle_streaming_indicator_import(hx_api_object, iocs):
	for (_, ioc) in iocs.items():
		# Add category for IOCs that don't have, i.e. OpenIOC 1.1 import
		if not ioc.get('category', False):
			ioc['category'] = 'Custom'
		if not ioc.get('description', False):
			ioc['description'] = ""
		if not ioc.get('uri_name', False):
			ioc['uri_name'] = _
		# only import custom 
		if ioc['category'].lower() == 'custom':
				# create the new indicator.  If this is an update, the orginal will be removed below.
				(ret, _, response_data) = hx_api_object.restAddStreamingIndicator(
												ioc_category=ioc['category'], 
												display_name=ioc['name'], 
												create_text=session['ht_user'], 
												platforms=ioc['platforms'], 
												description='{0}\n\nImported from {1}'.format(ioc['description'], ioc['uri_name']))
				if ret:
					new_ioc_id = response_data['id']
					
					# Convert realtime format to streaming format
					if not 'conditions' in ioc:
						ioc['conditions'] = []
					if 'presence' in ioc:
						ioc['conditions'].extend(ioc['presence'])
					if 'execution' in ioc:
						ioc['conditions'].extend(ioc['execution'])
						
					for condition in ioc['conditions']:
						mytests = {"tests": []}
						for test in condition:
							mytests['tests'].append({
								"token": 		 test.get('token', ''),		# purposefully provide a default that will fail insert
								"operator": 	 test.get('operator', ''),  # purposefully provide a default that will fail insert
								"type": 		 test.get('type', ''), 		# purposefully provide a default that will fail insert
								"value": 		 test.get('value', ''),		# purposefully provide a default that will fail insert
								"preservecase":  test.get('preservecase', False),
								"negate":		 test.get('negate', False)
							})
							
						(ret, _, response_data) = hx_api_object.restAddStreamingCondition(ioc['category'], new_ioc_id, 'condition', mytests)
						if not ret:
							# Remove the new indicator if condition push was unsuccessful.  Note that this will remove any conditions that were attached
							# ahead of this failure
							(ret, _, response_data) = hx_api_object.restDeleteStreamingIndicator(ioc['category'], new_ioc_id)
							app.logger.info(format_activity_log(msg="streaming rule action", reason="unable to import indicator", action="import", name=ioc['name'], user=session['ht_user'], controller=session['hx_ip']))
							break
					if ret:	
						app.logger.info(format_activity_log(msg="streaming rule action", reason="imported indicator", action="import", name=ioc['name'], user=session['ht_user'], controller=session['hx_ip']))
				else:
					# failed to create IOC
					app.logger.info(format_activity_log(msg="streaming rule action", reason="unable to import indicator", action="import", name=ioc['name'], user=session['ht_user'], controller=session['hx_ip']))
	return					

########################
# Indicator categories #
########################
@ht_api.route('/api/v{0}/indicator_category/get_edit_policies'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicator_category_get_edit_policies(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restListCategories()
	if ret:
		mycategories = {}
		for category in response_data['data']['entries']:
			mycategories[category['_id']] = category['ui_edit_policy']

	(r, rcode) = create_api_response(ret, response_code, mycategories)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicator_category/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicator_category_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restDeleteCategory(request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="rule category action", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicator_category/list'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicator_category_list(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restListCategories()
	(r, rcode) = create_api_response(ret, response_code, response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicator_category/new'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicator_category_new(hx_api_object):
	mycategory_options = {
		"ui_edit_policy": HXAPI.compat_str(request.args.get('edit_policy')),
		"retention_policy": HXAPI.compat_str(request.args.get('retention_policy')),
	}
	(ret, response_code, response_data) = hx_api_object.restCreateCategory(request.args.get('name'), category_options=mycategory_options)
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="rule category action", action="new", name=request.args.get('name'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

##############
# Conditions #
##############
@ht_api.route('/api/v{0}/conditions/get'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_conditions_get(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetConditionDetails(request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

###################
# Indicator queue #
###################
@ht_api.route('/api/v{0}/indicatorqueue/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicatorqueue_remove(hx_api_object):
	r = hxtool_global.hxtool_db.ruleRemove(request.args.get('id'))
	app.logger.info(format_activity_log(msg="rule queue action", action="remove", name=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicatorqueue/view'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicatorqueue_view(hx_api_object):
	r = hxtool_global.hxtool_db.ruleGet(request.args.get('id'))
	return(app.response_class(response=r, status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicatorqueue/approve'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicatorqueue_approve(hx_api_object):
	r = hxtool_global.hxtool_db.ruleUpdateState(request.args.get('id'), 1)
	r = hxtool_global.hxtool_db.ruleAddLog(request.args.get('id'), "User " + session['ht_user'] + " approved this request")
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicatorqueue/deny'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicatorqueue_deny(hx_api_object):
	r = hxtool_global.hxtool_db.ruleUpdateState(request.args.get('id'), 2)
	r = hxtool_global.hxtool_db.ruleAddLog(request.args.get('id'), "User " + session['ht_user'] + " denied this request")
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicatorqueue/import'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_indicatorqueue_import(hx_api_object):

	fc = request.files['ruleImport']
	iocs = json.loads(fc.read().decode(default_encoding))
	
	for iockey in iocs:
		hxtool_global.hxtool_db.ruleAdd(session['ht_profileid'], iocs[iockey]['name'], iocs[iockey]['category'], iocs[iockey]['platforms'], session['ht_user'], HXAPI.b64(json.dumps(iocs[iockey])), "add")
		
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

##############
# Indicators #
##############
@ht_api.route('/api/v{0}/indicators/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicators_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetUrl(request.args.get('url'), method="DELETE")
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="rule action", action="remove", name=request.args.get('url'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicators/get/conditions'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_indicators_get_conditions(hx_api_object):
	url = request.args.get('url')
	(ret, response_code, condition_class_presence) = hx_api_object.restGetUrl(url + '/conditions/presence', include_params = True)
	(ret, response_code, condition_class_execution) = hx_api_object.restGetUrl(url + '/conditions/execution', include_params = True)

	myconditions = { "presence": condition_class_presence, "execution": condition_class_execution }

	(r, rcode) = create_api_response(ret, response_code, myconditions)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicators/export'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_indicators_export(hx_api_object):
	iocList = request.json
	for uuid, ioc in iocList.items():
		(ret, response_code, response_data) = hx_api_object.restListIndicators(filter_term = { 'uri_name' : ioc['uri_name'] })
		if ret:
			iocList[uuid]['description'] = response_data['data']['entries'][0]['description']
			iocList[uuid]['create_text'] = response_data['data']['entries'][0]['create_text']
		(ret, response_code, response_data) = hx_api_object.restGetCondition(ioc['category'], ioc['uri_name'], 'execution')
		if ret:
			for item in response_data['data']['entries']:
				if not 'execution' in iocList[uuid].keys():
					iocList[uuid]['execution'] = []
				iocList[uuid]['execution'].append(item['tests'])
		(ret, response_code, response_data) = hx_api_object.restGetCondition(ioc['category'], ioc['uri_name'], 'presence')
		if ret:
			for item in response_data['data']['entries']:
				if not 'presence' in iocList[uuid].keys():
					iocList[uuid]['presence'] = []
				iocList[uuid]['presence'].append(item['tests'])

	
	buffer = BytesIO()
	if len(iocList.keys()) == 1:
		iocfname = iocList[list(iocList.keys())[0]]['uri_name'] + ".rule"
		buffer.write(json.dumps(iocList, indent=4, ensure_ascii=False).encode(default_encoding))
	else:
		iocfname = "multiple_indicators.zip"
		with zipfile.ZipFile(buffer, 'w') as zf:
			for ioc in iocList:
				zf.writestr(iocList[ioc]['uri_name'] + '.rule', json.dumps({ ioc : iocList[ioc] }, indent=4, ensure_ascii=False).encode(default_encoding))
		zf.close()

	buffer.seek(0)
	
	app.logger.info(format_activity_log(msg="rule action", action="export", name=iocfname, user=session['ht_user'], controller=session['hx_ip']))
	return send_file(buffer, download_name=iocfname, as_attachment=True)

@ht_api.route('/api/v{0}/indicators/import'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_indicators_import(hx_api_object):
	files = request.files.getlist('ruleImport')
	
	import_platform = request.form.get('platform', '')
	if import_platform == "all":
		import_platform = ['win', 'osx', 'linux']
	else:
		import_platform = [import_platform]
	
	for file in files:
		file_content = file.read().decode(default_encoding)
		try: 
			iocs = json.loads(file_content)
		except json.decoder.JSONDecodeError:
			iocs = openioc_to_hxioc(file_content, import_platform)
			if iocs is None:
				app.logger.warn(format_activity_log(msg="rule action fail", reason="{} is not a valid Endpoint Security (HX) JSON or OpenIOC 1.1 indicator." .format(file.filename), action="import", user=session['ht_user'], controller=session['hx_ip']))
				continue
		
		for iockey in iocs:
			# Default to custom if no category is in the IOC content
			# and no category is sent in the request
			if iocs[iockey].get('category', None) is None:
				iocs[iockey]['category'] = request.form.get('category', 'Custom')
			
			# Check if category exists
			category_exists = False
			(ret, response_code, response_data) = hx_api_object.restListCategories(limit = 1, filter_term={'name' : iocs[iockey]['category']})
			if ret:
				# As it turns out, filtering by name also returns partial matches. However the exact match seems to be the 1st result
				category_exists = (len(response_data['data']['entries']) == 1 and response_data['data']['entries'][0]['name'].lower() == iocs[iockey]['category'].lower())
				if not category_exists:
					app.logger.info(format_activity_log(msg="rule action", action="new", name=iocs[iockey]['name'], user=session['ht_user'], controller=session['hx_ip']))
					(ret, response_code, response_data) = hx_api_object.restCreateCategory(HXAPI.compat_str(iocs[iockey]['category']))
					category_exists = ret
				
				if category_exists:
					(ret, response_code, response_data) = hx_api_object.restAddIndicator(iocs[iockey]['category'], iocs[iockey]['name'], create_text=iocs[iockey].get('create_text', None) or session['ht_user'], platforms=iocs[iockey]['platforms'], description=iocs[iockey].get('description', None))
					if ret:
						ioc_guid = response_data['data']['_id']
						
						if 'presence' in iocs[iockey].keys():
							for p_cond in iocs[iockey]['presence']:
								data = json.dumps(p_cond)
								data = """{"tests":""" + data + """}"""
								(ret, response_code, response_data) = hx_api_object.restAddCondition(iocs[iockey]['category'], ioc_guid, 'presence', data)
								if not ret:
									app.logger.warn(format_activity_log(msg="rule action fail", reason="failed to create presence condition", action="import", name=iocs[iockey]['name'], user=session['ht_user'], controller=session['hx_ip']))

						if 'execution' in iocs[iockey].keys():
							for e_cond in iocs[iockey]['execution']:
								data = json.dumps(e_cond)
								data = """{"tests":""" + data + """}"""
								(ret, response_code, response_data) = hx_api_object.restAddCondition(iocs[iockey]['category'], ioc_guid, 'execution', data)
								if not ret:
									app.logger.warn(format_activity_log(msg="rule action fail", reason="failed to create execution condition", action="import", name=iocs[iockey]['name'], user=session['ht_user'], controller=session['hx_ip']))
				
						app.logger.info(format_activity_log(msg="rule action", action="import", name=iocs[iockey]['name'], user=session['ht_user'], controller=session['hx_ip']))
				else:
					app.logger.warn(format_activity_log(msg="rule action fail", reason="unable to create category", action="import", name=iocs[iockey]['name'], user=session['ht_user'], controller=session['hx_ip']))
			else:
				app.logger.info(format_activity_log(msg="rule action", reason="unable to import indicator", action="import", name=iocs[iockey]['name'], user=session['ht_user'], controller=session['hx_ip']))

	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/indicators/new'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_indicators_new(hx_api_object):

	mydata = json.loads(request.form.get('rule'))

	if mydata['platform'] == "all":
		chosenplatform = ['win', 'osx', 'linux']
	else:
		chosenplatform = [mydata['platform']]

	myrule = {}
	myrule['name'] = mydata['name']
	myrule['category'] = mydata['category']
	myrule['platforms'] = chosenplatform
	myrule['description'] = mydata['description']
	myrule['presence'] = []
	myrule['execution'] = []

	for key, value in mydata.items():
		if key not in ['name', 'category', 'platform', 'description']:
			(iocguid, ioctype) = key.split("_")

			if ioctype == "presence":
				mycondition = []
				for condition in value:
					mycondition.append({
						"token" : condition['group'] + "/" + condition['field'],
						"operator" : condition['operator'],
						"type" : condition['type'],
						"value" : condition['data'],
						"preservecase" : condition['case'],
						"negate" : condition['negate']
						})
				myrule['presence'].append(mycondition)

			elif ioctype == "execution":
				mycondition = []
				for condition in value:
					mycondition.append({
						"token" : condition['group'] + "/" + condition['field'],
						"operator" : condition['operator'],
						"type" : condition['type'],
						"value" : condition['data'],
						"preservecase" : condition['case'],
						"negate" : condition['negate']
						})
				myrule['execution'].append(mycondition)

	# TODO: Disable for now
	#hxtool_global.hxtool_db.ruleAdd(session['ht_profileid'], mydata['name'], mydata['category'], chosenplatform, session['ht_user'], HXAPI.b64(json.dumps(myrule)), "add")

	# REMOVE SOON
	(ret, response_code, response_data) = hx_api_object.restAddIndicator(mydata['category'], mydata['name'], session['ht_user'], chosenplatform, description=mydata['description'])
	if ret:
		ioc_guid = response_data['data']['_id']

		for key, value in mydata.items():
			if key not in ['name', 'category', 'platform', 'description']:
				(iocguid, ioctype) = key.split("_")
				mytests = {"tests": []}
				for entry in value:
					if not entry['negate'] and not entry['case']:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data']})
					elif entry['negate'] and not entry['case']:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data'], "negate": True})
					elif entry['case'] and not entry['negate']:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data'], "preservecase": True})
					else:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data'], "negate": True, "preservecase": True})

				(ret, response_code, response_data) = hx_api_object.restAddCondition(mydata['category'], ioc_guid, ioctype, json.dumps(mytests))
				if not ret:
					# Remove the indicator if condition push was unsuccessful
					(ret, response_code, response_data) = hx_api_object.restDeleteIndicator(mydata['category'], ioc_guid)
					return ('failed to create indicator conditions, check your conditions', 500)
		# All OK
		app.logger.info(format_activity_log(msg="rule action", action="new", name=mydata['name'], category=mydata['category'], user=session['ht_user'], controller=session['hx_ip']))
		return ('', 204)
	else:
		# Failed to create indicator
		app.logger.warn(format_activity_log(msg="rule action", action="new", reason="failed to create indicator", user=session['ht_user'], controller=session['hx_ip']))
		return ('failed to create indicator', 500)

@ht_api.route('/api/v{0}/indicators/edit'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_indicators_edit(hx_api_object):

	mydata = json.loads(request.form.get('rule'))

	# Get the original URI
	myOriginalURI = mydata['iocuri']
	myOriginalCategory = mydata['originalcategory']
	myState = True

	if mydata['platform'] == "all":
		chosenplatform = ['win', 'osx', 'linux']
	else:
		chosenplatform = [mydata['platform']]

	(ret, response_code, response_data) = hx_api_object.restAddIndicator(mydata['category'], mydata['name'], session['ht_user'], chosenplatform, description=mydata['description'])
	if ret:
		myNewURI = response_data['data']['_id']
		for key, value in mydata.items():
			if key not in ['name', 'category', 'platform', 'originalname', 'originalcategory', 'iocuri', 'description']:
				(iocguid, ioctype) = key.split("_")
				mytests = {"tests": []}
				for entry in value:
					if not entry['negate'] and not entry['case']:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data']})
					elif entry['negate'] and not entry['case']:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data'], "negate": True})
					elif entry['case'] and not entry['negate']:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data'], "preservecase": True})
					else:
						mytests['tests'].append({"token": entry['group'] + "/" + entry['field'], "type": entry['type'], "operator": entry['operator'], "value": entry['data'], "negate": True, "preservecase": True})

				(ret, response_code, response_data) = hx_api_object.restAddCondition(mydata['category'], myNewURI, ioctype, json.dumps(mytests))
				if not ret:
					# Condition was not added successfully set state to False to prevent the original indicator from being removed
					myState = False
					return('failed to create indicator conditions, check your conditions', 500)
		# Everything is OK
		if myState:
			# Remove the original indicator
			(ret, response_code, response_data) = hx_api_object.restDeleteIndicator(myOriginalCategory, myOriginalURI)

		app.logger.info(format_activity_log(msg="rule action", action="edit", name=mydata['name'], category=mydata['category'], user=session['ht_user'], controller=session['hx_ip']))
		return('', 204)
	else:
		# Failed to create indicator
		return('failed to create indicator',500)

#################################
# Custom configuration channels #
#################################
@ht_api.route('/api/v{0}/ccc/new'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_ccc_new(hx_api_object):

	mydata = json.loads(request.form.get('channel'))

	(ret, response_code, response_data) = hx_api_object.restNewConfigChannel(
		mydata['name'], 
		mydata['description'], 
		mydata['priority'], 
		mydata['hostsets'], 
		mydata['confjson']
		)

	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="custom configuration", action="new", name=mydata['name'], user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/ccc/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_ccc_remove(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restDeleteConfigChannel(request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	app.logger.info(format_activity_log(msg="custom configuration", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/ccc/get'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_ccc_get(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restGetConfigChannelConfiguration(request.args.get('id'))
	(r, rcode) = create_api_response(ret, response_code, response_data)
	return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

############
# Stacking #
############
@ht_api.route('/api/v{0}/stacking/stacktypes'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_stacking_stacktypes(hx_api_object):
	mystacktypes = list(hxtool_data_models.stack_types.keys())
	return(app.response_class(response=json.dumps(mystacktypes), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/stacking/new'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_stacking_new(hx_api_object):
	stack_type = hxtool_data_models.stack_types.get(request.form['stack_type'])
	if stack_type:
		with open(combine_app_path('scripts', stack_type['script']), 'r') as f:
			script_xml = f.read()
			f.close()
		hostset_id = int(request.form['stackhostset'])
		bulk_download_eid = submit_bulk_job(script_xml, hostset_id = hostset_id, task_profile = "stacking", comment = "HXTool Stacking Job: {}".format(stack_type['name']))
		ret = hxtool_global.hxtool_db.stackJobCreate(session['ht_profileid'], bulk_download_eid, request.form['stack_type'])
		app.logger.info(format_activity_log(msg="stacking", action="new", hostsetid=hostset_id, type=request.form['stack_type'], user=session['ht_user'], controller=session['hx_ip']))
		return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/stacking/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_stacking_remove(hx_api_object):
	stack_job = hxtool_global.hxtool_db.stackJobGet(request.args.get('id'))
	if stack_job:
		ret = True
		bulk_download_job = hxtool_global.hxtool_db.bulkDownloadGet(bulk_download_eid = stack_job['bulk_download_eid'])
		if bulk_download_job and 'bulk_acquisition_id' in bulk_download_job:
			(ret, response_code, response_data) = hx_api_object.restDeleteJob('acqs/bulk', bulk_download_job['bulk_acquisition_id'])
			hxtool_global.hxtool_db.bulkDownloadDelete(bulk_download_job.doc_id)
			(r, rcode) = create_api_response(ret, response_code, response_data)
		else:
			(r, rcode) = create_api_response()
			
		hxtool_global.hxtool_db.stackJobDelete(stack_job.doc_id)
		
		app.logger.info(format_activity_log(msg="stacking", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
		return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

@ht_api.route('/api/v{0}/stacking/stop'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_stacking_stop(hx_api_object):
	stack_job = hxtool_global.hxtool_db.stackJobGet(stack_job_eid = request.args.get('id'))
	if stack_job:
		bulk_download_job = hxtool_global.hxtool_db.bulkDownloadGet(bulk_download_eid = stack_job['bulk_download_eid'])
		if bulk_download_job and 'bulk_acquisition_id' in bulk_download_job:
			(ret, response_code, response_data) = hx_api_object.restCancelJob('acqs/bulk', bulk_download_job['bulk_acquisition_id'])
			hxtool_global.hxtool_db.bulkDownloadUpdate(bulk_download_job.doc_id, stopped = True)
			(r, rcode) = create_api_response(ret, response_code, response_data)
		else:
			(r, rcode) = create_api_response()
			
		hxtool_global.hxtool_db.stackJobStop(stack_job_eid = stack_job.doc_id)
			
		app.logger.info(format_activity_log(msg="stacking", action="stop", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
		return(app.response_class(response=json.dumps(r), status=rcode, mimetype='application/json'))

##########################
# Multi-file acquisition #
##########################
@ht_api.route('/api/v{0}/acquisition/multi/file_listing/new'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_acquisition_multi_file_listing(hx_api_object):

	# Get Acquisition Options from Form
	display_name = request.form['listing_name']
	path = request.form['listing_path']
	regex = request.form['listing_regex']
	md5_hashes = request.form['listing_md5s']
	hostset = int(request.form['hostset'])
	use_api_mode = ('use_raw_mode' not in request.form)
	
	# Build a script from the template
	with open(combine_app_path('scripts/files_listing_template.json'), 'r') as f:
		script_json = json.load(f)
		f.close()
	
	script_json['commands'][0]['parameters'].append({
		'name' : 'Path', 
		'value' : path
	})
	
	regex = request.form['listing_regex']
	if regex:
		try:
			re.compile(regex)
			script_json['commands'][0]['parameters'].append({
				'name' : 'Regex', 
				'value' : regex
			})	
		except re.error:
			return(app.response_class(response=json.dumps("Invalid regular expression."), status=400, mimetype='application/json'))
	
	if not use_api_mode:
		script_json['commands'][0]['name'] = "files-raw"
		script_json['commands'][0]['parameters'].extend([{
			'name' : 'Active Files',
			'value' : True
		}, {
			'name' : 'Deleted Files',
			'value' : True
		}, {
			'name' : 'Parse NTFS INDX Buffers',
			'value' : True
		}])
	
	if md5_hashes:
		valid_hashes, md5_hashes = validate_hashes(md5_hashes, "MD5")

		if valid_hashes:
			script_json['commands'][0]['parameters'].append({
				'name' : 'Filter MD5', 
				'value' : md5_hashes
			})
		else:	
			return(app.response_class(response=json.dumps("{} is an invalid MD5 hash.".format(md5_hashes)), status=400, mimetype='application/json'))
	
	if not display_name:
		display_name = 'hostset: {0} path: {1} regex: {2}'.format(hostset, path, regex)
	
	bulk_download_eid = submit_bulk_job(json.dumps(script_json), hostset_id = hostset, task_profile = "file_listing")
	ret = hxtool_global.hxtool_db.fileListingCreate(session['ht_profileid'], session['ht_user'], bulk_download_eid, path, regex, -1, display_name, api_mode=use_api_mode)
	app.logger.info(format_activity_log(msg="multi-file listing acquisition", action="new", hostset_id=hostset, user=session['ht_user'], controller=session['hx_ip']))
	return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/multi/file_listing/stop'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_multi_file_listing_stop(hx_api_object):
	file_listing_job = hxtool_global.hxtool_db.fileListingGetById(request.args.get('id'))
	if file_listing_job:
		bulk_download_job = hxtool_global.hxtool_db.bulkDownloadGet(file_listing_job['bulk_download_eid'])
		(ret, response_code, response_data) = hx_api_object.restCancelJob('acqs/bulk', bulk_download_job['bulk_acquisition_id'])
		if ret:
			hxtool_global.hxtool_db.fileListingStop(file_listing_job.doc_id)
			hxtool_global.hxtool_db.bulkDownloadUpdate(file_listing_job['bulk_download_eid'], stopped = True)
			app.logger.info(format_activity_log(msg="multi-file listing acquisition", action="stop", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
			return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))
		else:
			return(app.response_class(response=json.dumps(response_data), status=response_code, mimetype='application/json'))
	return(app.response_class(response=json.dumps("File listing job not found."), status=404, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/multi/file_listing/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_multi_file_listing_remove(hx_api_object):
	file_listing_job = hxtool_global.hxtool_db.fileListingGetById(request.args.get('id'))
	if file_listing_job:
		bulk_download_job = hxtool_global.hxtool_db.bulkDownloadGet(file_listing_job['bulk_download_eid'])
		if bulk_download_job.get('bulk_acquisition_id', None):
			(ret, response_code, response_data) = hx_api_object.restDeleteJob('acqs/bulk', bulk_download_job['bulk_acquisition_id'])
		hxtool_global.hxtool_db.bulkDownloadDelete(file_listing_job['bulk_download_eid'])
		hxtool_global.hxtool_db.fileListingDelete(file_listing_job.doc_id)
		app.logger.info(format_activity_log(msg="multi-file listing acquisition", action="remove", id=request.args.get('id'), user=session['ht_user'], controller=session['hx_ip']))
		return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/multi/mf/stop'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_multi_mf_stop(hx_api_object):
	mf_job = hxtool_global.hxtool_db.multiFileGetById(request.args.get('id'))
	if mf_job:
		success = True
		#TODO: Stop each file acquisition or handle solely in remove?
		if success:
			hxtool_global.hxtool_db.multiFileStop(mf_job.doc_id)
			app.logger.info(format_activity_log(msg="multi-file acquisition", action="stop", id=mf_job.doc_id, user=session['ht_user'], controller=session['hx_ip']))
			return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/multi/mf/remove'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_multi_mf_remove(hx_api_object):
	mf_job = hxtool_global.hxtool_db.multiFileGetById(request.args.get('id'))
	if mf_job:
		success = True
		for f in mf_job['files']:
			uri = 'acqs/files/{0}'.format(f['acquisition_id'])
			(ret, response_code, response_data) = hx_api_object.restDeleteFile(uri)
			#TODO: Replace with delete of file from record
			if not f['downloaded']:
				hxtool_global.hxtool_db.multiFileUpdateFile(session['ht_profileid'], mf_job.doc_id, f['acquisition_id'])
			# If the file acquisition no longer exists on the controller(404), then we should delete it from our DB anyway.
			if not ret and response_code != 404:
				app.logger.error("Failed to remove file acquisition {0} from the HX controller, response code: {1}".format(f['acquisition_id'], response_code))
				success = False		
		if success:
			hxtool_global.hxtool_db.multiFileDelete(mf_job.doc_id)
			app.logger.info(format_activity_log(msg="multi-file acquisition", action="remove", id=mf_job.doc_id, user=session['ht_user'], controller=session['hx_ip']))
			return(app.response_class(response=json.dumps("OK"), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/acquisition/multi/mf/new'.format(HXTOOL_API_VERSION), methods=['POST'])
@valid_session_required
def hxtool_api_acquisition_multi_mf_new(hx_api_object):

	#TODO: Make Configurable both from GUI and config file?
	if request.method == 'POST':
		MAX_FILE_ACQUISITIONS = 50
		
		display_name = ('display_name' in request.form) and request.form['display_name'] or "{0} job at {1}".format(session['ht_user'], datetime.datetime.now())
		use_api_mode = ('use_raw_mode' not in request.form)

		# Collect User Selections
		file_jobs, choices, listing_ids = [], {}, set([])
		#choice_re = re.compile('^choose_file_(\d+)_(\d+)$')
		for k, v in list(request.form.items()):
			if k.startswith("choose_file"):
				(fl_id, myindex) = k[12:].split("_")
			#	fl_id = int(m.group(1))
				listing_ids.add(fl_id)
				choices.setdefault(fl_id, []).append(int(myindex))
		if choices:
			choice_files, agent_ids = [], {}
			for fl_id, file_ids in list(choices.items()):
				# Gather the records for files to acquire from the file listing
				file_listing = hxtool_global.hxtool_db.fileListingGetById(fl_id)
				if not file_listing:
					app.logger.warn('File Listing %s does not exist - User: %s@%s:%s', session['ht_user'], fl_id, hx_api_object.hx_host, hx_api_object.hx_port)
					continue
				choice_files = [file_listing['files'][i] for i in file_ids if i <= len(file_listing['files'])]
				multi_file_eid = hxtool_global.hxtool_db.multiFileCreate(session['ht_user'], session['ht_profileid'], display_name=display_name, file_listing_id=file_listing.doc_id, api_mode=use_api_mode)
				# Create a data acquisition for each file from its host
				for cf in choice_files:
					if cf['hostname'] in agent_ids:
						agent_id = agent_ids[cf['hostname']]
					else:
						(ret, response_code, response_data) = hx_api_object.restListHosts(search_term = cf['hostname'])
						agent_id = agent_ids[cf['hostname']] = response_data['data']['entries'][0]['_id']
					path_split_char = '\\'
					if cf['FullPath'].startswith('/'):
						path_split_char = '/'
					path, filename = cf['FullPath'].rsplit(path_split_char, 1)
					(ret, response_code, response_data) = hx_api_object.restAcquireFile(agent_id, path, filename, use_api_mode)
					if ret:
						acq_id = response_data['data']['_id']
						job_record = {
							'acquisition_id' : int(acq_id),
							'hostname': cf['hostname'],
							'path': cf['FullPath'],
							'downloaded': False
						}
						mf_job_id = hxtool_global.hxtool_db.multiFileAddJob(multi_file_eid, job_record)
						file_acquisition_task = hxtool_scheduler_task(session['ht_profileid'], "File Acquisition: {}".format(cf['hostname']))
						file_acquisition_task.add_step(file_acquisition_task_module, kwargs = {
															'multi_file_eid' : multi_file_eid,
															'file_acquisition_id' : int(acq_id),
															'host_name' : cf['hostname']
														})
						hxtool_global.hxtool_scheduler.add(file_acquisition_task)
						#app.logger.info('File acquisition requested from host %s at path %s- User: %s@%s:%s - host: %s', cf['hostname'], cf['FullPath'], session['ht_user'], hx_api_object.hx_host, hx_api_object.hx_port, agent_id)
						app.logger.info(format_activity_log(msg="file acquistion requested", fromhost=cf['hostname'], path=cf['FullPath'], host=agent_id, user=session['ht_user'], controller=session['hx_ip']))
						file_jobs.append(acq_id)
						if len(file_jobs) >= MAX_FILE_ACQUISITIONS:
							break
					else:
						#TODO: Handle fail
						pass
			if file_jobs:
				app.logger.info(format_activity_log(msg="multi-file acquisition", action="new", user=session['ht_user'], controller=session['hx_ip']))
		else:
			app.logger.error(format_activity_log(error="Multi-file acquisition failed, no files were selected.", action="new", user=session['ht_user'], controller=session['hx_ip']))
			
	return redirect("/multifile", code=302)

##############
# Datatables #
##############
@ht_api.route('/api/v{0}/datatable_multi_filelisting'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_multi_filelisting(hx_api_object):
	profile_id = session['ht_profileid']
	data_rows = []
	for j in hxtool_global.hxtool_db.fileListingList(profile_id):
		job = dict(j)
		job.update({'id': j.doc_id})
		job['state'] = ("STOPPED" if job['stopped'] else "RUNNING")
		job['file_count'] = len(job.pop('files'))

		# Completion rate
		bulk_download = hxtool_global.hxtool_db.bulkDownloadGet(bulk_download_eid = job['bulk_download_eid'])
		if bulk_download:
			hosts_completed = len([_ for _ in bulk_download['hosts'] if bulk_download['hosts'][_]['downloaded']])
			job_progress = 0
			if hosts_completed > 0:
				job_progress = int(hosts_completed / float(len(bulk_download['hosts'])) * 100)
			if 'display_name' not in job:
				job['display_name'] = 'hostset {0}, path: {1} regex: {2}'.format(bulk_download['hostset_id'] , job['cfg']['path'], job['cfg']['regex'])
		else:
			job_progress = job['file_count'] > 1 and 100 or 0
			if 'display_name' not in job:
				job['display_name'] = 'path: {0} regex: {1}'.format(job['cfg']['path'], job['cfg']['regex'])
		
		job['progress'] = "<div class='htMyBar htBarWrap'><div class='htBar' id='file_listing_prog_" + str(job['id']) + "' data-percent='" + str(job_progress) + "'></div></div>"
		job['DT_RowId'] = job['id']
		data_rows.append(job)
	return(app.response_class(response=json.dumps({'data': data_rows}), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_multi_multifile'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_multi_multifile(hx_api_object):
	profile_id = session['ht_profileid']
	data_rows = []
	for mf in hxtool_global.hxtool_db.multiFileList(profile_id):
		job = dict(mf)
		hosts_completed = len([_ for _ in job['files'] if _['downloaded']])
		job.update({
			'id': mf.doc_id,
			'state': ("STOPPED" if job['stopped'] else "RUNNING"),
			'file_count': len(job['files']),
			'mode': ('api_mode' in job and job['api_mode']) and 'API' or 'RAW'
		})

		# Completion rate
		job_progress = (int(job['file_count']) > 0) and  int(hosts_completed / float(job['file_count']) * 100) or 0
		job['progress'] = "<div class='htMyBar htBarWrap'><div class='htBar' id='multi_file_prog_" + str(job['id']) + "' data-percent='" + str(job_progress) + "'></div></div>"

		job['DT_RowId'] = job['id']
		data_rows.append(job)
	return(app.response_class(response=json.dumps({'data': data_rows}), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_stacking'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_stacking(hx_api_object):
	mydata = {}
	mydata['data'] = []

	stack_jobs = hxtool_global.hxtool_db.stackJobList(session['ht_profileid'])
	for job in stack_jobs:
		bulk_download = hxtool_global.hxtool_db.bulkDownloadGet(bulk_download_eid = job['bulk_download_eid'])

		job_progress = 0
		if 'hosts' in job:
			hosts_completed = len([_ for _ in job['hosts'] if _['processed']])
		else:
			hosts_completed = len([_ for _ in bulk_download['hosts'] if bulk_download['hosts'][_]['downloaded']])
		if hosts_completed > 0:
			job_progress = int(hosts_completed / float(len(bulk_download['hosts'])) * 100)

		mydata['data'].append({
			"DT_RowId": job.doc_id,
			"create_timestamp": HXAPI.compat_str(job['create_timestamp']),
			"update_timestamp": HXAPI.compat_str(job['update_timestamp']),
			"stack_type": job['stack_type'],
			"state": ("STOPPED" if job['stopped'] else "RUNNING"),
			"profile_id": HXAPI.compat_str(job['profile_id']),
			"bulk_acquisition_id": (HXAPI.compat_str(bulk_download['bulk_acquisition_id']) if 'bulk_acquisition_id' in bulk_download else "N/A"),
			"hostset_id": HXAPI.compat_str(bulk_download['hostset_id']),
			"job_progress": HXAPI.compat_str(job_progress)
			})

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_ccc'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_ccc(hx_api_object):
	mydata = {}
	mydata['data'] = []

	(ret, response_code, response_data) = hx_api_object.restListCustomConfigChannels()
	if ret:
		for channel in response_data['data']['entries']:

			myhostsets = []
			for hostset in channel['host_sets']:
				myhostsets.append(hostset['name'])

			mydata['data'].append({
				"DT_RowId": channel['_id'],
				"name": channel['name'],
				"description": channel['description'],
				"priority": channel['priority'],
				"host_sets": myhostsets,
				"create_time": channel['create_time'],
				"create_actor": channel['create_actor']['username']
				})

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable/agentstatus/csv'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_agentstatus_csv(hx_api_object):
	mydata = {}
	mydata['data'] = []

	myField = request.args.get('field')
	myPattern = request.args.get('pattern')

	(hret, hresponse_code, hresponse_data) = hx_api_object.restListHosts(limit=200000, filter_term={ myField: myPattern })

	for host in hresponse_data['data']['entries']:
		if '.' in myField:
			item1, item2 = myField.split(".")
			mydata['data'].append({
				"DT_RowId": host['_id'],
				"hostname": host['hostname'],
				item1 + "_" + item2: host[item1][item2]
				})
		else:
			mydata['data'].append({
				"DT_RowId": host['_id'],
				"hostname": host['hostname'],
				myField: host[myField]
				})

	csvkeys = mydata['data'][0].keys()
	writer_file =  StringIO()
	writer = csv.DictWriter(writer_file, csvkeys, dialect='excel', delimiter=',')
	writer.writeheader()
	writer.writerows(mydata['data'])

	mem = BytesIO()
	mem.write(writer_file.getvalue().encode('utf-8'))
	mem.seek(0)
	writer_file.close()

	return send_file(mem, download_name="agent_statistics_" + myField + ".csv", as_attachment=True)

@ht_api.route('/api/v{0}/datatable/agentstatus'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_agentstatus(hx_api_object):
	mydata = {}
	mydata['data'] = []

	myField = request.args.get('field')
	myPattern = request.args.get('pattern')

	(hret, hresponse_code, hresponse_data) = hx_api_object.restListHosts(limit=5000, filter_term={ myField: myPattern })

	for host in hresponse_data['data']['entries']:
		if '.' in myField:
			item1, item2 = myField.split(".")
			mydata['data'].append({
				"DT_RowId": host['_id'],
				"hostname": host['hostname'],
				item1 + "_" + item2: host[item1][item2]
				})
		else:
			mydata['data'].append({
				"DT_RowId": host['_id'],
				"hostname": host['hostname'],
				myField: host[myField]
				})

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable/avcontent'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_avcontent_detail(hx_api_object):
	mydata = {}
	mydata['data'] = []

	myversion = request.args.get('version')

	(hret, hresponse_code, hresponse_data) = hx_api_object.restListHosts()
	for host in hresponse_data['data']['entries']:
		(ret, response_code, response_data) = hx_api_object.restGetHostSysinfo(host['_id'])
		if ret and js_path(response_data, "data.malware.av.content.version", None) is not None:
			if myversion == response_data['data']['malware']['av']['content']['version']:
				mydata['data'].append({
					"hostname": host['hostname'],
					"agentid": host['_id'],
					"content_version": myversion
					})
		else:
			if myversion == "none":
				mydata['data'].append({
					"hostname": host['hostname'],
					"agentid": host['_id'],
					"content_version": myversion
					})

	del hresponse_data

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable/avengine'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_avengine_detail(hx_api_object):
	mydata = {}
	mydata['data'] = []

	myversion = request.args.get('version')

	(hret, hresponse_code, hresponse_data) = hx_api_object.restListHosts()
	for host in hresponse_data['data']['entries']:
		(ret, response_code, response_data) = hx_api_object.restGetHostSysinfo(host['_id'])
		if ret and js_path(response_data, "data.malware.av.engine.version", None) is not None:
			if myversion == response_data['data']['malware']['av']['engine']['version']:
				mydata['data'].append({
					"hostname": host['hostname'],
					"agentid": host['_id'],
					"engine_version": myversion
					})
		else:
			if myversion == "none":
				mydata['data'].append({
					"hostname": host['hostname'],
					"agentid": host['_id'],
					"engine_version": myversion
					})

	del hresponse_data

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable/avstatus'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_avstatus_detail(hx_api_object):
	mydata = {}
	mydata['data'] = []

	mystate = request.args.get('state')

	(hret, hresponse_code, hresponse_data) = hx_api_object.restListHosts()
	for host in hresponse_data['data']['entries']:
		(ret, response_code, response_data) = hx_api_object.restGetHostSysinfo(host['_id'])
		if 'MalwareProtectionStatus' in response_data['data']:
			if mystate == response_data['data']['MalwareProtectionStatus']:
				mydata['data'].append({
					"hostname": host['hostname'],
					"agentid": host['_id'],
					"state": mystate
					})
		else:
			if mystate == "none":
				mydata['data'].append({
					"hostname": host['hostname'],
					"agentid": host['_id'],
					"state": mystate
					})

	del hresponse_data

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_categories'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_categories(hx_api_object):
	mydata = {}
	mydata['data'] = []

	(ret, response_code, response_data) = hx_api_object.restListCategories()
	if ret:
		for category in response_data['data']['entries']:
			mydata['data'].append({
				"uri_name": category['uri_name'],
				"DT_RowId": category['_id'],
				"name": category['name'],
				"retention_policy": category['retention_policy'],
				"ui_edit_policy": category['ui_edit_policy'],
				"ui_signature_enabled": category['ui_signature_enabled'],
				"ui_source_alerts_enabled": category['ui_source_alerts_enabled'],
				"share_mode": category['share_mode']
				})

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_indicators'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_indicators(hx_api_object):
	
	mydata = {}
	mydata['data'] = []

	(ret, response_code, response_data) = hx_api_object.restListIndicators()
	if ret:
		for indicator in response_data['data']['entries']:
			mydata['data'].append({
				"DT_RowId": indicator['_id'],
				"url": indicator['url'],
				"uri_name" : indicator['uri_name'],
				"display_name": indicator['name'],
				"active_since": indicator['active_since'],
				"category_name": indicator['category']['name'],
				"created_by": indicator['created_by'],
				"platforms": indicator['platforms'],
				"active_conditions": indicator['stats']['active_conditions'],
				"alerted_agents": indicator['stats']['alerted_agents'],
				"category_id": indicator['category']['_id']
				})

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_hosts'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_hosts(hx_api_object):
	
	mydata = {}
	mydata['data'] = []

	(ret, response_code, response_data) = hx_api_object.restListHosts(search_term = request.args.get('q'))
	if ret:
		for host in response_data['data']['entries']:
			mydata['data'].append({
				"DT_RowId": host['_id'],
				"hostname": host['hostname'],
				"domain": host['domain'],
				"agent_version": host['agent_version'],
				"last_poll_timestamp": host['last_poll_timestamp'],
				"last_poll_ip": host['last_poll_ip'],
				"product_name": host['os']['product_name'],
				"patch_level": host['os']['patch_level']
				})

	return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_hosts_with_alerts'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_hosts_with_alerts(hx_api_object):
	if request.method == 'GET':

		myhosts = []

		(ret, response_code, response_data) = hx_api_object.restListHosts(limit=request.args.get('limit'), sort_term="stats.alerts+descending")
		if ret:
			for host in response_data['data']['entries']:
				myhosts.append([host['hostname'] + "___" + host['_id'], host['stats']['alerts']])
		else:
			return('', 500)

		mydata = {"data": myhosts[:10]}

		return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_alerts_host'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_alerts_host(hx_api_object):
	if request.method == 'GET':

		myalerts = {"data": []}

		(ret, response_code, response_data) = hx_api_object.restGetAlerts(limit=request.args.get('limit'), filter_term={ "agent._id": request.args.get("host") })
		if ret:
			for alert in response_data['data']['entries']:
				tname = "N/A"
				if alert['source'] in hxtool_global.hx_alert_types:
					tname = js_path(alert, hxtool_global.hx_alert_types.get(alert['source'])['threat_key'])
					if alert['source'] == "EXD":
						tname = "Exploit detected in process {}".format(tname)
					# Handle missing indicator object when multiple IOCs hit. ENDPT-52003
					elif alert['source'] == "IOC" and alert.get("indicator", None) is None:
						(cret, cresponse_code, cresponse_data) = hx_api_object.restGetIndicatorFromCondition(alert['condition']['_id'])
						if cret and len(cresponse_data['data']['entries']) > 0:
							tlist = [ _['name'] for _ in cresponse_data['data']['entries'] ]
							tname = "; ".join(tlist)
						else:
							tname = "N/A"

				myalerts['data'].append({
					"DT_RowId": alert['_id'],
					"event_at": HXAPI.dt_to_str(HXAPI.gtNoUs(alert['event_at'])),
					"source": alert['source'],
					"threat": tname,
					"resolution": alert['resolution']
				})
		else:
			return('', 500)

		return(app.response_class(response=json.dumps(myalerts), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_alerts'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_alerts(hx_api_object):
	if request.method == 'GET':

		myalerts = {"data": []}

		if 'source' in request.args:
			(ret, response_code, response_data) = hx_api_object.restGetAlerts(limit=request.args.get('limit'), filter_term={ "source": request.args.get("source") })
		else:
			(ret, response_code, response_data) = hx_api_object.restGetAlerts(limit=request.args.get('limit'))

		if ret:
			for alert in response_data['data']['entries']:
				# Query host object
				hresponse_data = False
				if hxtool_global.hxtool_config.get_child_item('apicache', 'enabled', False):
					hresponse_data = hxtool_global.hxtool_db.cacheGet(session['ht_profileid'], "host", alert['agent']['_id'])
				if hresponse_data == False:
					(hret, hresponse_code, hresponse_data) = hx_api_object.restGetHostSummary(alert['agent']['_id'])

				if ret:
					hostname = hresponse_data['data']['hostname']
					domain = hresponse_data['data']['domain']
					hid = hresponse_data['data']['_id']
					aid = alert['_id']
				else:
					hostname = "unknown"
					domain = "unknown"

				tname = "N/A"
				if alert['source'] in hxtool_global.hx_alert_types:
					tname = js_path(alert, hxtool_global.hx_alert_types.get(alert['source'])['threat_key'])
					if alert['source'] == "EXD":
						tname = "Exploit detected in process {}".format(tname)
					# Handle missing indicator object when multiple IOCs hit. ENDPT-52003
					elif alert['source'] == "IOC" and alert.get("indicator", None) is None:
						(cret, cresponse_code, cresponse_data) = hx_api_object.restGetIndicatorFromCondition(alert['condition']['_id'])
						if cret and len(cresponse_data['data']['entries']) > 0:
							tlist = [ _['name'] for _ in cresponse_data['data']['entries'] ]
							tname = "; ".join(tlist)
						else:
							tname = "N/A"
							
				myalerts['data'].append([HXAPI.compat_str(hostname) + "___" + HXAPI.compat_str(hid) + "___" + HXAPI.compat_str(aid), domain, alert['reported_at'], alert['source'], tname, alert['resolution']])
		else:
			return('', 500)

		return(app.response_class(response=json.dumps(myalerts), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_alerts_full'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_alerts_full(hx_api_object):
	if request.method == 'GET':

		myalerts = {"data": []}

		# hosts and ioc cache
		myhosts = {}
		myiocs = {}

		myfilters = {}
		if 'source' in request.args:
			myfilters['source'] = [request.args.get("source")]

		if 'resolution' in request.args:
			myfilters['resolution'] = request.args.get("resolution")

		if 'limit' in request.args:
			mylimit = int(request.args.get("limit"))
		else:
			mylimit = None

		if 'hostname' in request.args:
			(ret, response_code, response_data) = hx_api_object.restListHosts(search_term = request.args.get('hostname'))
			if ret:
				myhostlist = []
				for hostname in response_data['data']['entries']:
					myhostlist.append(hostname['_id'])
				myfilters['agent._id'] = myhostlist

		if len(myfilters) > 0:
			(ret, response_code, response_data) = hx_api_object.restGetAlertsTime(request.args.get('startDate'), request.args.get('endDate'), filters=myfilters, limit=mylimit)
		else:
			(ret, response_code, response_data) = hx_api_object.restGetAlertsTime(request.args.get('startDate'), request.args.get('endDate'), limit=mylimit)
		if ret:

			# Check if we need to match alertname
			if 'alertname' in request.args:

				myalertname = request.args.get("alertname")
				myMatches = []

				for alert in response_data:
					if alert['source'] == "MAL":
						for mymalinfo in alert['event_values']['detections']['detection']:
							try:
								if myalertname in mymalinfo['infection']['infection-name']:
									myMatches.append(alert)
							except(KeyError):
								continue
					if alert['source'] == "EXD":
						if myalertname in alert['event_values']['process_name']:
							myMatches.append(alert)
					if alert['source'] == "IOC":
						if alert['condition']['_id'] not in myiocs:
							# Query IOC object since we do not have it in memory
							(cret, cresponse_code, cresponse_data) = hx_api_object.restGetIndicatorFromCondition(alert['condition']['_id'])
							if cret:
								myiocs[alert['condition']['_id']] = cresponse_data['data']['entries'][0]
								tname = cresponse_data['data']['entries'][0]['name']
							else:
								tname = "N/A"
						else:
							tname = myiocs[alert['condition']['_id']]['name']
							if myalertname in tname:
								myMatches.append(alert)

				# overwrite data with our filtered list
				response_data = myMatches


			# Check if we need to match md5hash
			if 'md5hash' in request.args:

				myhash = request.args.get("md5hash")
				myMatches = []
				myIOCfields = ["fileWriteEvent/md5", "processEvent/md5"]

				for alert in response_data:
					if alert['source'] == "IOC":
						try:
							for mykey in myIOCfields:
								if alert['event_values'][mykey] == myhash:
									myMatches.append(alert)
						except(KeyError):
							continue

					elif alert['source'] == "EXD":
						EXDMatch = False
						for detail in alert['event_values']['analysis_details']:
							for itemkey, itemvalue in detail[detail['detail_type']].items():
								if (itemkey == "md5sum" and itemvalue == myhash):
									EXDMatch = True
								else:
									if itemkey == "processinfo":
										try:
											if detail[detail['detail_type']]['processinfo']['md5sum'] == myhash:
												EXDMatch = True
										except(KeyError):
											continue
						if EXDMatch:
							myMatches.append(alert)

					elif alert['source'] == "MAL":
						for detection in alert['event_values']['detections']['detection']:
							for myobjkey, myobjval in detection['infected-object'].items():
								if myobjkey == "file-object":
									try:
										if myobjval['md5sum'] == myhash:
											myMatches.append(alert)
									except(KeyError):
										continue
					else:
						continue

				response_data = myMatches


			# Get annotations from DB and store in memory
			myannotations = {}
			dbannotations = hxtool_global.hxtool_db.alertList(session['ht_profileid'])
			for annotation in dbannotations:
				if not annotation['hx_alert_id'] in myannotations.keys():
					myannotations[annotation['hx_alert_id']] = {"max_state": 0, "count": len(annotation['annotations'])}

				for item in annotation['annotations']:
					if item['state'] > myannotations[annotation['hx_alert_id']]['max_state']:
						myannotations[annotation['hx_alert_id']]['max_state'] = item['state']

			for alert in response_data:

				if alert['_id'] in myannotations.keys():
					annotation_count = myannotations[alert['_id']]['count']
					annotation_max_state = myannotations[alert['_id']]['max_state']
				else:
					annotation_count = 0
					annotation_max_state = 0

				
				if alert['agent']['_id'] not in myhosts:
					# Query host object since we do not have it in memory
					(hret, hresponse_code, hresponse_data) = hx_api_object.restGetHostSummary(alert['agent']['_id'])
					if ret:
						myhosts[alert['agent']['_id']] = hresponse_data['data']
				
				hostname = myhosts[alert['agent']['_id']]['hostname']
				domain = myhosts[alert['agent']['_id']]['domain']
				hid = myhosts[alert['agent']['_id']]['_id']
				aid = alert['_id']
				if HXAPI.compat_str(myhosts[alert['agent']['_id']]['os']['product_name']).startswith('Windows'):
					platform = "win"
				elif HXAPI.compat_str(myhosts[alert['agent']['_id']]['os']['product_name']).startswith('Mac'):
					platform = "mac"
				else:
					platform = "linux"

				
				tname = "N/A"
				if alert['source'] in hxtool_global.hx_alert_types:
					tname = js_path(alert, hxtool_global.hx_alert_types.get(alert['source'])['threat_key'])
					if alert['source'] == "EXD":
						tname = "Exploit detected in process {}".format(tname)
					# Handle missing indicator object when multiple IOCs hit. ENDPT-52003
					elif alert['source'] == "IOC" and alert.get("indicator", None) is None:
						(cret, cresponse_code, cresponse_data) = hx_api_object.restGetIndicatorFromCondition(alert['condition']['_id'])
						if cret and len(cresponse_data['data']['entries']) > 0:
							tlist = [ _['name'] for _ in cresponse_data['data']['entries'] ]
							tname = "; ".join(tlist)
						else:
							tname = "N/A"

				myalerts['data'].append({
					"DT_RowId": alert['_id'],
					"platform": platform,
					"hostname": HXAPI.compat_str(hostname) + "___" + HXAPI.compat_str(hid) + "___" + HXAPI.compat_str(aid),
					"domain": domain,
					"event_at": alert['event_at'],
					"matched_at": alert['matched_at'],
					"reported_at": alert['reported_at'],
					"containment_state": alert['agent']['containment_state'],
					"age": HXAPI.prettyTime(HXAPI.gt(alert['event_at'])),
					"source": alert['source'],
					"threat": tname,
					"resolution": alert['resolution'],
					"annotation_max_state": annotation_max_state,
					"annotation_count": annotation_count,
					"action": alert['_id']
					})
		else:
			return('', 500)

		return(app.response_class(response=json.dumps(myalerts), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_scripts'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_scripts(hx_api_object):
	if request.method == 'GET':
		myscripts = hxtool_global.hxtool_db.scriptList()
		return(app.response_class(response=json.dumps(myscripts), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_openioc'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_openioc(hx_api_object):
	if request.method == 'GET':
		myiocs = hxtool_global.hxtool_db.oiocList()
		return(app.response_class(response=json.dumps(myiocs), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_taskprofiles'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_taskprofiles(hx_api_object):
	if request.method == 'GET':
		mytaskprofiles = hxtool_global.hxtool_db.taskProfileList()
		# TODO: filter passwords and keys in task params
		return(app.response_class(response=json.dumps(mytaskprofiles), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_acqs'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_acqs(hx_api_object):
	if request.method == 'GET':
			myacqs = {"data": []}
			(ret, response_code, response_data) = hx_api_object.restListAllAcquisitions(limit=500)
			if ret:
				for acq in response_data['data']['entries']:
					if acq['type'] != "bulk":
						hresponse_data = False
						if hxtool_global.hxtool_config.get_child_item('apicache', 'enabled', False):
							hresponse_data = hxtool_global.hxtool_db.cacheGet(session['ht_profileid'], "host", acq['host']['_id'])
						if hresponse_data == False:
							(hret, hresponse_code, hresponse_data) = hx_api_object.restGetHostSummary(acq['host']['_id'])
						if ret:
							request_user = "N/A"
							acq_url = None
							if 'url' in acq['acq']:
								acq_url = acq['acq']['url']
							else:
								acq_url = "/hx/api/v3/acqs/{}/{}".format(acq['type'], HXAPI.compat_str(acq['acq']['_id']))
							a_response_data = False
							if hxtool_global.hxtool_config.get_child_item('apicache', 'enabled', False):
								a_response_data = hxtool_global.hxtool_db.cacheGet(session['ht_profileid'], acq['type'], acq['acq']['_id'])
							if a_response_data == False:
								(a_ret, a_response_code, a_response_data) = hx_api_object.restGetUrl(acq_url)
							else:
								a_ret = True

							if a_ret:
								request_user = a_response_data['data']['request_actor']['username']
							myacqs['data'].append({
								"DT_RowId": acq['acq']['_id'],
								"type": acq['type'],
								"request_time": acq['request_time'],
								"request_user": request_user,
								"state": acq['state'],
								"hostname": hresponse_data['data']['hostname'] + "___" + hresponse_data['data']['_id'],
								"domain": hresponse_data['data']['domain'],
								"containment_state": hresponse_data['data']['containment_state'],
								"last_poll_timestamp": hresponse_data['data']['last_poll_timestamp'],
								"platform": hresponse_data['data']['os']['platform'],
								"product_name": hresponse_data['data']['os']['product_name'],
								"action": acq['acq']['_id']
							})
				return(app.response_class(response=json.dumps(myacqs), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_acqs_host'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_acqs_host(hx_api_object):
	if request.method == 'GET':
			myacqs = {"data": []}
			(ret, response_code, response_data) = hx_api_object.restListAllAcquisitions(limit=500, filter_term={ "host._id": request.args.get("host") })
			if ret:
				for acq in response_data['data']['entries']:
					if 'url' in acq['acq'].keys():
						myacqurl = acq['acq']['url']
					elif (acq['type'] == "live"):
						myacqurl = "/hx/api/v3/acqs/live/" + HXAPI.compat_str(acq['acq']['_id'])
					else:
						myacqurl = False

					myacqs['data'].append({
						"DT_RowId": myacqurl,
						"type": acq['type'],
						"request_time": HXAPI.dt_to_str(HXAPI.gtNoUs(acq['request_time'])),
						"state": acq['state']
					})
				return(app.response_class(response=json.dumps(myacqs), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_es'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_es(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restListSearches()
	if ret:
		mysearches = {"data": []}
		for search in response_data['data']['entries']:

			# Check for the existance of displayname, HX 4.5.0 and older doesn't have it
			if search['settings']['displayname']:
				displayname = search['settings']['displayname']
			else:
				displayname = "N/A"

			mysearches['data'].append({
				"DT_RowId": search['_id'],
				"state": search['state'],
				"displayname": displayname,
				"update_time": search['update_time'],
				"create_time": search['create_time'],
				"update_actor": search['update_actor']['username'],
				"create_actor": search['create_actor']['username'],
				"input_type": search['input_type'],
				"host_set": search['host_set']['name'],
				"host_set_id": search['host_set']['_id'],
				"stat_new": search['stats']['running_state']['NEW'],
				"stat_queued": search['stats']['running_state']['QUEUED'],
				"stat_failed": search['stats']['running_state']['FAILED'],
				"stat_complete": search['stats']['running_state']['COMPLETE'],
				"stat_aborted": search['stats']['running_state']['ABORTED'],
				"stat_cancelled": search['stats']['running_state']['CANCELLED'],
				"stat_hosts": search['stats']['hosts'],
				"stat_skipped_hosts": search['stats']['skipped_hosts'],
				"stat_searchstate_pending": search['stats']['search_state']['PENDING'],
				"stat_searchstate_matched": search['stats']['search_state']['MATCHED'],
				"stat_searchstate_notmatched": search['stats']['search_state']['NOT_MATCHED'],
				"stat_searchstate_error": search['stats']['search_state']['ERROR'],
				"mode": search['settings']['mode']
			})
		return(app.response_class(response=json.dumps(mysearches), status=200, mimetype='application/json'))
	else:
		return('HX API Call failed',500)

@ht_api.route('/api/v{0}/datatable_indicatorqueue'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_indicatorqueue(hx_api_object):
	indicators = hxtool_global.hxtool_db.ruleList(session['ht_profileid'])

	myrules = {"data": []}

	for indicator in indicators:
		myrules['data'].append({
			"DT_RowId" : indicator['id'],
			"name" : indicator['name'],
			"method" : indicator['method'],
			"category" : indicator['category'],
			"platform" : indicator['platform'],
			"state" : indicator['state'],
			"create_user" : indicator['create_user'],
			"update_user" : indicator['update_user'],
			"create_timestamp" : indicator['create_timestamp'],
			"update_timestamp" : indicator['update_timestamp'],
			"log" : indicator['log'],
			"action" : indicator['id'],
			})
	return(app.response_class(response=json.dumps(myrules), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/datatable_bulk'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_bulk(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restListBulkAcquisitions()
	if ret:
		mybulk = {"data": []}
		for acq in response_data['data']['entries']:

			# Find the host-set id. We have to do this because in some cases hostset is kept in comment and in some cases not.
			# TODO: remove host set in comment code after several releases. This should no longer be used.
			if acq['host_set']:
				try:
					myhostsetid = acq['host_set']['_id']
				except(KeyError):
					myhostsetid = False
			else:
				if acq['comment']:
					try:
						mycommentdata = json.loads(acq['comment'])
					except(ValueError):
						myhostsetid = False
					else:
						myhostsetid = mycommentdata['hostset_id']
				else:
					myhostsetid = False

			# Find hostset name
			if myhostsetid:
				if myhostsetid != 9:
					(hret, hresponse_code, hresponse_data) = hx_api_object.restListHostsets(filter_term={"_id": myhostsetid})
					if ret and len(hresponse_data['data']['entries']) > 0:
						try:
							myhostsetname = hresponse_data['data']['entries'][0]['name']
						except(KeyError):
							myhostsetname = HXAPI.compat_str(myhostsetid)
					else:
						myhostsetname = HXAPI.compat_str(myhostsetid)
				else:
					myhostsetname = "All Hosts"
			else:
				myhostsetname = "N/A"

			# Comlete rate
			total_size = acq['stats']['running_state']['NEW'] + acq['stats']['running_state']['QUEUED'] + acq['stats']['running_state']['FAILED'] + acq['stats']['running_state']['ABORTED'] + acq['stats']['running_state']['DELETED'] + acq['stats']['running_state']['REFRESH'] + acq['stats']['running_state']['CANCELLED'] + acq['stats']['running_state']['COMPLETE']
			if total_size == 0:
				completerate = 0
			else:
				completerate = int(float(acq['stats']['running_state']['COMPLETE']) / float(total_size) * 100)
			
			if completerate > 100:
				completerate = 100

			# Download rate
			bulk_download = hxtool_global.hxtool_db.bulkDownloadGet(profile_id = session['ht_profileid'], bulk_acquisition_id = acq['_id'])

			if bulk_download:
				total_hosts = len(bulk_download['hosts'])
				hosts_completed = len([_ for _ in bulk_download['hosts'] if bulk_download['hosts'][_]['downloaded']])
				if total_hosts > 0 and hosts_completed > 0:
					
					dlprogress = int(float(hosts_completed) / total_hosts * 100)
								
					if dlprogress > 100:
						dlprogress = 100

				else:
					dlprogress = 0
			else:
				dlprogress = "N/A"

			# Handle buttons
			myaction = acq['_id']
			if bulk_download and bulk_download['task_profile']:
				if bulk_download['task_profile'] in ["file_listing","stacking"]:
					myaction = bulk_download['task_profile']

			mybulk['data'].append({
				"DT_RowId": acq['_id'],
				"state": acq['state'],
				"comment": acq['comment'],
				"hostset": myhostsetname,
				"create_time": acq['create_time'],
				"update_time": acq['update_time'],
				"create_actor": acq['create_actor']['username'],
				"stat_runtime_avg": acq['stats']['run_time']['avg'],
				"stat_runtime_min": acq['stats']['run_time']['min'],
				"stat_runtime_max": acq['stats']['run_time']['max'],
				"total_size": acq['stats']['total_size'],
				"task_size_avg": acq['stats']['task_size']['avg'],
				"task_size_min": acq['stats']['task_size']['min'],
				"task_size_max": acq['stats']['task_size']['max'],
				"running_state_new": acq['stats']['running_state']['NEW'],
				"running_state_queued": acq['stats']['running_state']['QUEUED'],
				"running_state_failed": acq['stats']['running_state']['FAILED'],
				"running_state_complete": acq['stats']['running_state']['COMPLETE'],
				"running_state_aborted": acq['stats']['running_state']['ABORTED'],
				"running_state_cancelled": acq['stats']['running_state']['CANCELLED'],
				"completerate": completerate,
				"downloadrate": dlprogress,
				"action": myaction
			})
		return(app.response_class(response=json.dumps(mybulk), status=200, mimetype='application/json'))
	else:
		return('HX API Call failed',500)

@ht_api.route('/api/v{0}/datatable_es_result_types'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_es_result_types(hx_api_object):
	if request.args.get('id'):
		mytypes = {}
		(ret, response_code, response_data) = hx_api_object.restGetSearchResults(request.args.get('id'), limit=30000)
		if ret:
			for host in response_data['data']['entries']:
				for event in host['results']:
					if not event['type'] in mytypes:
						mytypes[event['type']] = ['hostname']
					for key, val in event.items():
						if not key.replace(" ", "_") in mytypes[event['type']]:
							if key == "data":
								for datakey in val.keys():
									if not datakey.replace(" ", "_") in mytypes[event['type']]:
										mytypes[event['type']].append(datakey.replace(" ", "_"))
							elif key == "type":
								mytypes[event['type']].append(key.replace(" ", "_"))


			return(app.response_class(response=json.dumps(mytypes), status=200, mimetype='application/json'))
		else:
			return('HX API Call failed', 500)
	else:
		return('Missing search id', 404)

@ht_api.route('/api/v{0}/datatable_es_result'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def datatable_es_result(hx_api_object):
	if request.args.get('id') and request.args.get('type'):
		myresult = {"data": []}
		(ret, response_code, response_data) = hx_api_object.restGetSearchResults(request.args.get('id'), limit=30000)
		if ret:
			for host in response_data['data']['entries']:
				for event in host['results']:
					if event['type'] == request.args.get('type'):
						mytempdict = {"DT_RowId": host['host']['_id'], "hostname": host['host']['hostname'] + "___" + host['host']['_id']}
						for eventitemkey, eventitemvalue in event.items():
							if eventitemkey == "data":
								for datakey, datavalue in eventitemvalue.items():
									mytempdict[datakey.replace(" ", "_")] = datavalue
							elif eventitemkey == "id":
								continue
							else:
								mytempdict[eventitemkey.replace(" ", "_")] = eventitemvalue
						myresult['data'].append(mytempdict)

			return(app.response_class(response=json.dumps(myresult), status=200, mimetype='application/json'))
		else:
			return('HX API Call failed', 500)
	else:
		return('Missing search id or type', 404)

###########
# ChartJS #
###########
@ht_api.route('/api/v{0}/chartjs_agentstatus'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_agentstatus(hx_api_object):
	rData = {}
	(ret, response_code, response_data) = hx_api_object.restListHosts()
	if ret:
		myField = request.args.get('field')
		myData = {}

		for host in response_data['data']['entries']:
			if "." in myField:
				item1, item2 = myField.split(".")
				if host[item1][item2] not in myData.keys():
					myData[host[item1][item2]] = 0
				myData[host[item1][item2]] += 1
			else:
				if host[myField] not in myData.keys():
					myData[host[myField]] = 0
				myData[host[myField]] += 1

		del response_data

		myPattern = ["#0fb8dc", "#006b8c", "#fb715e", "#59dc90", "#11a962", "#99ddff", "#ffe352", "#f0950e", "#ea475b", "#00cbbe"]
		random.shuffle(myPattern)

		rData['labels'] = list(myData.keys())
		rData['datasets'] = []
		rData['datasets'].append({
			"label": myField,
			"backgroundColor": myPattern,
			"borderColor": "#0d1a2b",
			"borderWidth": 5,
			"data": list(myData.values())
			})

	return(app.response_class(response=json.dumps(rData), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/chartjs_malwarecontent'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_malwarecontent(hx_api_object):
	if request.method == 'GET':
		
		myContent = defaultdict(int)
		myData = {}
		myData['labels'] = []
		myData['datasets'] = []


		try:
			(ret, response_code, response_data) = hx_api_object.restAgentSysinfo()
			if ret:
				for sysinfo in response_data['data']['entries']:
					if 'data' in sysinfo:
						myContent[js_path(sysinfo, "data.malware.av.content.version", "none")] +=1
					else:
						myContent['none'] += 1
		except NotImplementedError:
			(ret, response_code, response_data) = hx_api_object.restListHosts()
			if ret:
				for host in response_data['data']['entries']:
					(sret, sresponse_code, sresponse_data) = hx_api_object.restGetHostSysinfo(host['_id'])
					if sret:
						myContent[js_path(sresponse_data, "data.malware.av.content.version", "none")] += 1
					else:
						myContent['none'] += 1
			
			del response_data
		
		dataset = []
		mylist = []
		for ckey, cval in myContent.items():
			mylist.append({ "version": ckey, "count": cval })

		newlist = sorted(mylist, key=lambda k: k['count'])
		results = newlist[-10:]

		for entry in results:
			myData['labels'].append(entry['version'])
			dataset.append(entry['count'])

#		myPattern = get_N_HexCol(len(results))
		myPattern = ["#0fb8dc", "#006b8c", "#fb715e", "#59dc90", "#11a962", "#99ddff", "#ffe352", "#f0950e", "#ea475b", "#00cbbe"]

		myData['datasets'] = []
		myData['datasets'].append({
			"label": "content version",
			"backgroundColor": myPattern,
			"borderColor": "#0d1a2b",
			"borderWidth": 5,
			"data": dataset
			})

		return(app.response_class(response=json.dumps(myData), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/chartjs_malwareengine'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_malwareengine(hx_api_object):
	if request.method == 'GET':
		
		myContent = defaultdict(int)
		myData = {}
		myData['labels'] = []
		myData['datasets'] = []

		try:
			(ret, response_code, response_data) = hx_api_object.restAgentSysinfo()
			if ret:
				for sysinfo in response_data['data']['entries']:
					if 'data' in sysinfo:
						myContent[js_path(sysinfo, "data.malware.av.engine.version", "none")] +=1
					else:
						myContent['none'] += 1
		except NotImplementedError:
			(ret, response_code, response_data) = hx_api_object.restListHosts()
			if ret:
				for host in response_data['data']['entries']:
					(sret, sresponse_code, sresponse_data) = hx_api_object.restGetHostSysinfo(host['_id'])
					if sret:
						myContent[js_path(sresponse_data, "data.malware.av.engine.version", "none")] += 1
					else:
						myContent['none'] += 1

			del response_data

		dataset = []
		mylist = []
		for ckey, cval in myContent.items():
			mylist.append({ "version": ckey, "count": cval })

		newlist = sorted(mylist, key=lambda k: k['count'])
		results = newlist[-10:]

		for entry in results:
			myData['labels'].append(entry['version'])
			dataset.append(entry['count'])

		myPattern = ["#0fb8dc", "#006b8c", "#fb715e", "#59dc90", "#11a962", "#99ddff", "#ffe352", "#f0950e", "#ea475b", "#00cbbe"]

		myData['datasets'] = []
		myData['datasets'].append({
			"label": "engine version",
			"backgroundColor": myPattern,
			"borderColor": "#0d1a2b",
			"borderWidth": 5,
			"data": dataset
			})

		return(app.response_class(response=json.dumps(myData), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/chartjs_malwarestatus'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_malwarestatus(hx_api_object):
	if request.method == 'GET':
		
		myContent = defaultdict(int)
		myData = {}
		myData['labels'] = []
		myData['datasets'] = []
		
		# Try the /agents/sysinfo call on HX 5.0+
		try:
			(ret, response_code, response_data) = hx_api_object.restAgentSysinfo()
			if ret:
				for sysinfo in response_data['data']['entries']:
					if 'data' in sysinfo:
						myContent[sysinfo['data'].get('MalwareProtectionStatus', 'none')] +=1
					else:
						myContent['none'] += 1
			
		# Fall back to the old code
		except NotImplementedError:			
			(ret, response_code, response_data) = hx_api_object.restListHosts()
			if ret:
				for host in response_data['data']['entries']:
					(sret, sresponse_code, sresponse_data) = hx_api_object.restGetHostSysinfo(host['_id'])
					if sret and 'data' in sresponse_data:
						myContent[sresponse_data['data'].get('MalwareProtectionStatus', 'none')] += 1
					else:
						myContent['none'] += 1

			del response_data

		dataset = []
		mylist = []
		for ckey, cval in myContent.items():
			mylist.append({ "mode": ckey, "count": cval })

		newlist = sorted(mylist, key=lambda k: k['count'])
		results = newlist[-10:]

		for entry in results:
			myData['labels'].append(entry['mode'])
			dataset.append(entry['count'])

		myPattern = ["#0fb8dc", "#006b8c", "#fb715e", "#59dc90", "#11a962", "#99ddff", "#ffe352", "#f0950e", "#ea475b", "#00cbbe"]

		myData['datasets'] = []
		myData['datasets'].append({
			"label": "mode",
			"backgroundColor": myPattern,
			"borderColor": "#0d1a2b",
			"borderWidth": 5,
			"data": dataset
			})

		return(app.response_class(response=json.dumps(myData), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/enterprise_search/chartjs_searches'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_enterprise_search_chartjs_searches(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restListSearches()
	(r, rcode) = create_api_response(ret, response_code, response_data)
	if ret:
		mysearches = {}
		myGraphData = []
		myr = {}
		myr['labels'] = []
		myr['datasets'] = []

		startDate = datetime.datetime.strptime(request.args.get('startDate'), '%Y-%m-%d')
		endDate = datetime.datetime.strptime(request.args.get('endDate'), '%Y-%m-%d')
		delta = (endDate - startDate)

		# Generate data for all dates
		date_list = [endDate - datetime.timedelta(days=x) for x in range(0, delta.days + 1)]
		for date in date_list[::-1]:
			mysearches[date.strftime("%Y-%m-%d")] = 0

		for search in response_data['data']['entries']:

			if search['create_time'][0:10] in mysearches.keys():
				mysearches[search['create_time'][0:10]] += 1

		for key, val in mysearches.items():
			myr['labels'].append(key)
			myGraphData.append(val)

		myr['datasets'].append({
			"label": "Search count",
			"backgroundColor": "rgba(17, 169, 98, 0.2)",
			"borderWidth": 2,
			"borderColor": "#8fffc1",
			"pointStyle": "circle",
			"pointRadius": 2,
			"data": myGraphData
		})

		return(app.response_class(response=json.dumps(myr), status=rcode, mimetype='application/json'))
	else:
		return('HX API Call failed',500)

@ht_api.route('/api/v{0}/acquisition/bulk/chartjs_acquisitions'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def hxtool_api_acquisition_bulk_chartjs_acquisitions(hx_api_object):
	(ret, response_code, response_data) = hx_api_object.restListBulkAcquisitions()
	(r, rcode) = create_api_response(ret, response_code, response_data)
	if ret:
		mysearches = {}
		myGraphData = []
		myr = {}
		myr['labels'] = []
		myr['datasets'] = []

		startDate = datetime.datetime.strptime(request.args.get('startDate'), '%Y-%m-%d')
		endDate = datetime.datetime.strptime(request.args.get('endDate'), '%Y-%m-%d')
		delta = (endDate - startDate)

		# Generate data for all dates
		date_list = [endDate - datetime.timedelta(days=x) for x in range(0, delta.days + 1)]
		for date in date_list[::-1]:
			mysearches[date.strftime("%Y-%m-%d")] = 0

		for search in response_data['data']['entries']:

			if search['create_time'][0:10] in mysearches.keys():
				mysearches[search['create_time'][0:10]] += 1

		for key, val in mysearches.items():
			myr['labels'].append(key)
			myGraphData.append(val)

		myr['datasets'].append({
			"label": "Bulk count",
			"backgroundColor": "rgba(17, 169, 98, 0.2)",
			"borderWidth": 2,
			"borderColor": "#8fffc1",
			"pointStyle": "circle",
			"pointRadius": 2,
			"data": myGraphData
		})

		return(app.response_class(response=json.dumps(myr), status=rcode, mimetype='application/json'))
	else:
		return('HX API Call failed',500)

@ht_api.route('/api/v{0}/chartjs_hosts_initial_agent_checkin'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_hosts_initial_agent_checkin(hx_api_object):

	myhosts = {}
	myhosts['labels'] = []
	myhosts['datasets'] = []
	mycount = {}

	# Get all dates and calculate delta
	startDate = datetime.datetime.strptime(request.args.get('startDate'), '%Y-%m-%d')
	endDate = datetime.datetime.strptime(request.args.get('endDate'), '%Y-%m-%d')
	delta = (endDate - startDate)

	# Generate data for all dates
	date_list = [endDate - datetime.timedelta(days=x) for x in range(0, delta.days + 1)]
	for date in date_list[::-1]:
		mycount[date.strftime("%Y-%m-%d")] = 0

	(ret, response_code, response_data) = hx_api_object.restListHosts(limit=100000)
	if ret:
		for host in response_data['data']['entries']:
			if host['initial_agent_checkin'][0:10] in mycount.keys():
				mycount[host['initial_agent_checkin'][0:10]] += 1
		
		del response_data
		
		myGraphData = []
		for key, stats in mycount.items():
			myhosts['labels'].append(key)
			myGraphData.append(stats)

		myhosts['datasets'].append({
			"label": "Provisioned endpoints",
			"backgroundColor": "rgba(17, 169, 98, 0.2)",
			"borderWidth": 2,
			"borderColor": "#8fffc1",
			"pointStyle": "circle",
			"pointRadius": 2,
	        "data": myGraphData
			})
	else:
		return('', 500)

	return(app.response_class(response=json.dumps(myhosts), status=200, mimetype='application/json'))

@ht_api.route('/api/v{0}/chartjs_events_timeline'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_events_timeline(hx_api_object):

	mydates = {
		'labels' : [],
		'datasets' : []
	}
	mycount = {}

	# Get all dates and calculate delta
	startDate = datetime.datetime.strptime(request.args.get('startDate'), '%Y-%m-%d')
	endDate = datetime.datetime.strptime(request.args.get('endDate'), '%Y-%m-%d')
	delta = (endDate - startDate)

	# Generate data for all dates
	date_list = [endDate - datetime.timedelta(days=x) for x in range(0, delta.days + 1)]
	for date in date_list[::-1]:
		mycount[date.strftime("%Y-%m-%d")] = { k : 0 for k in hxtool_global.hx_alert_types.keys() }

	# Get alerts
	(ret, response_code, response_data) = hx_api_object.restGetAlertsTime(request.args.get('startDate'), request.args.get('endDate'))
	if ret:
		for alert in response_data:
			# Make sure the date exists
			if not alert['event_at'][0:10] in mycount.keys():
				mycount[alert['event_at'][0:10]] = { k : 0 for k in hxtool_global.hx_alert_types.keys() }
			
			# Add stats for date
			mycount[alert['event_at'][0:10]][alert['source']] += 1

		stats_lists = { k : [] for k in hxtool_global.hx_alert_types.keys() }

		for key, stats in mycount.items():
			mydates['labels'].append(key)
			for k in hxtool_global.hx_alert_types.keys():
				stats_lists[k].append(stats[k])

		for k in hxtool_global.hx_alert_types.keys():
			mydates['datasets'].append({
			"label": hxtool_global.hx_alert_types[k]['label'],
			"backgroundColor": "rgba(17, 169, 98, 0.2)",
			"borderWidth": 2,
			"borderColor": "#8fffc1",
			"pointStyle": "circle",
			"pointRadius": 2,
			"data": stats_lists[k]
		})

		return(app.response_class(response=json.dumps(mydates), status=200, mimetype='application/json'))
	else:
		return('',500)

@ht_api.route('/api/v{0}/chartjs_host_alert_timeline'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_host_alert_timeline(hx_api_object):

	mydates = {
		'datasets' : []
	}
	
	stats_dict = {
		k : {
			"label": k,
			"backgroundColor": "rgba(17, 169, 98, 0.2)",
			"borderWidth": 2,
			"borderColor": "#8fffc1",
			"pointStyle": "circle",
			"pointRadius": 2,
			"data": [] }
			for k in hxtool_global.hx_alert_types.keys() 
	}
	

	(ret, response_code, response_data) = hx_api_object.restGetAlerts(filter_term={"agent._id": request.args.get("id")})
	if ret:
		for alert in response_data['data']['entries']:
			stats_dict[alert['source']]['data'].append({"x": alert['event_at'][0:19].replace("T", " "), "y": 1})
			
			
		for k, v in stats_dict:
			mydates['datasets'].append(v)

		return(app.response_class(response=json.dumps(mydates), status=200, mimetype='application/json'))
	else:
		return('',500)

@ht_api.route('/api/v{0}/chartjs_events_distribution'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_events_distribution(hx_api_object):

	mydata = {
		'labels' : [ k for k in hxtool_global.hx_alert_types.keys() ],
		'datasets' : []
	}
	mycount = {
		k : 0 for k in hxtool_global.hx_alert_types.keys()
	}

	# Get alerts
	(ret, response_code, response_data) = hx_api_object.restGetAlertsTime(request.args.get('startDate'), request.args.get('endDate'))
	if ret:
		for alert in response_data:
			# Make sure the key exists
			if not alert['source'] in mycount.keys():
				mycount[alert['source']] = 0

			# Add stats
			mycount[alert['source']] += 1

		mydata['datasets'].append({
			"label": "Alert count",
			"backgroundColor": "rgba(17, 169, 98, 0.2)",
			"borderColor": "#8fffc1",
			"borderWidth": 0.5,
			"data": [ mycount[k] for k in hxtool_global.hx_alert_types.keys() ]
		})

		return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))
	else:
		return('',500)

@ht_api.route('/api/v{0}/chartjs_inactive_hosts_per_hostset'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def chartjs_inactive_hosts_per_hostset(hx_api_object):

	myhosts = []
	
	(ret, response_code, response_data) = hx_api_object.restListHostsets()
	if ret:
		for hostset in response_data['data']['entries']:
			(hret, hresponse_code, hresponse_data) = hx_api_object.restListHosts(query_terms = {'host_sets._id' : hostset['_id']})
			if hret:
				now = datetime.datetime.utcnow()
				hcount = 0
				for host in hresponse_data['data']['entries']:
					x = (HXAPI.gt(host['last_poll_timestamp']))
					if (int((now - x).total_seconds())) > int(request.args.get('seconds')):
						hcount += 1
				
				del hresponse_data
				
				myhosts.append({"hostset": hostset['name'], "count": hcount})

		# Return the Vega Data
		newlist = sorted(myhosts, key=lambda k: k['count'])
		results = newlist[-10:]

		mydata = {}
		mydata['labels'] = []
		mydata['datasets'] = []

		tempData = []
		for setname in results[::-1]:
			mydata['labels'].append(setname['hostset'])
			tempData.append(setname['count'])

		mydata['datasets'].append({
			"label": "Missing hosts",
			"backgroundColor": "rgba(17, 169, 98, 0.2)",
			"borderColor": "#8fffc1",
			"borderWidth": 0.5,
			"data": tempData
		})	

		return(app.response_class(response=json.dumps(mydata), status=200, mimetype='application/json'))
	else:
		return('',500)

######################
# Profile Management #
######################
@ht_api.route('/api/v{0}/profile'.format(HXTOOL_API_VERSION), methods=['GET', 'PUT'])
def profile():
	if request.method == 'GET':
		profiles = hxtool_global.hxtool_db.profileList()
		return json.dumps({'data_count' :  len(profiles), 'data' : profiles})
	elif request.method == 'PUT':
		request_json = request.json
		if validate_json(['hx_name', 'hx_host', 'hx_port'], request_json):
			if hxtool_global.hxtool_db.profileCreate(request_json['hx_name'], request_json['hx_host'], request_json['hx_port']):
				logger.info("New controller profile added")
				return make_response_by_code(200)
		else:
			return make_response_by_code(400)
			
@ht_api.route('/api/v{0}/profile/<uuid:profile_id>'.format(HXTOOL_API_VERSION), methods=['GET', 'PUT', 'DELETE'])
def profile_by_id(profile_id):
	profile_id = str(profile_id)
	if request.method == 'GET':
		profile_object = hxtool_global.hxtool_db.profileGet(profile_id)
		if profile_object:
			return json.dumps({'data' : profile_object})
		else:
			return make_response_by_code(404)
	elif request.method == 'PUT':
		request_json = request.json
		if validate_json(['profile_id', 'hx_name', 'hx_host', 'hx_port'], request_json):
			if hxtool_global.hxtool_db.profileUpdate(request_json['_id'], request_json['hx_name'], request_json['hx_host'], request_json['hx_port']):
				logger.info("Controller profile %d modified.", profile_id)
				return make_response_by_code(200)
	elif request.method == 'DELETE':
		if hxtool_global.hxtool_db.profileDelete(profile_id):
			logger.info("Controller profile %s deleted.", profile_id)
			return make_response_by_code(200)
		else:
			return make_response_by_code(404)

####################
# Stacking Results #
####################
@ht_api.route('/api/v{0}/stacking/results/<stack_job_eid>'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def stack_job_results(hx_api_object, stack_job_eid):
	stack_job = hxtool_global.hxtool_db.stackJobGet(stack_job_eid = stack_job_eid)
	
	if stack_job is None:
		return make_response_by_code(404)

	if session['ht_profileid'] != stack_job['profile_id']:
		return make_response_by_code(401)
		
	ht_data_model = hxtool_data_models(stack_job['stack_type'])
	return ht_data_model.stack_data(stack_job['results'])	

#####################
# Cache API calls ###
#####################
@ht_api.route('/api/v{0}/cache/statistics'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def cache_statistics(hx_api_object):

	mystats = {}

	try:
		if hxtool_global.hxtool_config['apicache']['enabled']:
			mystats['enabled'] = True
		else:
			mystats['enabled'] = False
	except TypeError:
		mystats['enabled'] = False

	if mystats['enabled']:
		mystats['started'] = hxtool_global.apicache['started']
		mystats['types'] = hxtool_global.apicache['types']
		for k, v in hxtool_global.apicache['data'].items():
			mystats[k] = {}
			mystats[k]['settings'] = v['settings']
			mystats[k]['records processed'] = v['stats']['records']

		return(app.response_class(response=json.dumps(mystats), status=200, mimetype='application/json'))
	else:
		return(app.response_class(response=json.dumps("DISABLED"), status=200, mimetype='application/json'))

#######################
### X15 INTEGRATION ###
#######################
@ht_api.route('/api/v{0}/analysis/data'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def x15_analysis_data(hx_api_object):

	if hasattr(hxtool_global, 'hxtool_x15_object'):
		myres = {"data": hxtool_global.hxtool_x15_object.getAudits()}
		return(json.dumps(myres))
	else:
		return make_response_by_code(400)

@ht_api.route('/api/v{0}/analysis/auditmodules'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def x15_analysis_auditmodules(hx_api_object):

	if hasattr(hxtool_global, 'hxtool_x15_object'):
		myids = [int(x) for x in request.args.get('id').split(",")]
		myres = {"data": hxtool_global.hxtool_x15_object.getAuditModules(myids)}
		return(json.dumps(myres))
	else:
		return make_response_by_code(400)

@ht_api.route('/api/v{0}/analysis/auditdata'.format(HXTOOL_API_VERSION), methods=['GET'])
@valid_session_required
def x15_analysis_auditdata(hx_api_object):

	generatorMeta = {
		"eventbuffer": "eventitem"
	}

	if hasattr(hxtool_global, 'hxtool_x15_object'):
		mygenerators = request.args.get('generators').split(",")
		myids = [int(x) for x in request.args.get('id').split(",")]
		
		#myres = {"data": hxtool_global.hxtool_x15_object.getAuditData(mygenerators, myids)}
		myres = hxtool_global.hxtool_x15_object.getAuditData(mygenerators, myids)
		#myres = {"data": []}

		#import demjson

		for event in hxtool_global.hxtool_x15_object.getAuditData(mygenerators, myids):
			
			myjson = json.loads(event[next(iter(event))])

			#print((event[generatorMeta[event['generator']]]))


			#myres['data'].append({
			#	"" : event[generatorMeta[event['generator']]]
			#})

		#print(myres)
		return(json.dumps(myres))
		#return(myres)
	else:
		return make_response_by_code(400)

#######################
def create_api_response(ret = True, response_code = 200, response_data = False):

	api_response = {}
	api_response['api_success'] = ret
	api_response['api_response_code'] = response_code

	if response_data:
		api_response['api_response'] = json.dumps(response_data)

	rcode = 200
	if not ret and response_code:
		if response_code in [401, 404]:
			rcode = response_code
		else:
			rcode = 400

	return(api_response, rcode)

def submit_bulk_job(script_content, hostset_id = None, hxtool_hostgroup_id = None, start_time = None, schedule = None, comment = "HXTool Bulk Acquisition", download = True, task_profile = None, skip_base64 = False):
	bulk_download_eid = None
	
	bulk_acquisition_task = hxtool_scheduler_task(session['ht_profileid'], 'Bulk Acquisition ID: pending', start_time = start_time)
	if schedule:
		bulk_acquisition_task.set_schedule(**schedule)
	
	if download:
		bulk_download_eid = hxtool_global.hxtool_db.bulkDownloadCreate(session['ht_profileid'], hostset_id = hostset_id, task_profile = task_profile)
		bulk_acquisition_monitor_task = hxtool_scheduler_task(
											session['ht_profileid'], 
											'Bulk Acquisition Monitor Task', 
											parent_id = bulk_acquisition_task.task_id,
											start_time = bulk_acquisition_task.start_time
										)
	
		bulk_acquisition_monitor_task.add_step(
			bulk_download_monitor_task_module,
			kwargs = {
						'bulk_download_eid' : bulk_download_eid,
						'task_profile' : task_profile
			}
		)
		
		hxtool_global.hxtool_scheduler.add(bulk_acquisition_monitor_task)
		
		
	bulk_acquisition_task.add_step(
		bulk_acquisition_task_module, 
		kwargs = {
					'script' : script_content,
					'hostset_id' : hostset_id,
					'comment' : comment,
					'skip_base64' : skip_base64,
					'download' : download,
					'bulk_download_eid' : bulk_download_eid
		}
	)
		
	hxtool_global.hxtool_scheduler.add(bulk_acquisition_task)
	
	return bulk_download_eid