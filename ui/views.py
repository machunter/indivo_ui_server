"""
Views for Indivo JS UI

"""
# pylint: disable=W0311, C0301
# fixme: rm unused imports
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpRequest
from django.contrib.auth.models import User
from django.core.exceptions import *
from django.core.urlresolvers import reverse
from django.core import serializers
from django.db import transaction
from django.conf import settings

from django.views.static import serve
from django.template import Template, Context
from django.utils import simplejson
from django.utils.translation import ugettext as _

import xml.etree.ElementTree as ET
import urllib, re

import utils
from errors import ErrorStr

HTTP_METHOD_GET = 'GET'
HTTP_METHOD_POST = 'POST'
LOGIN_PAGE = 'ui/login'
DEBUG = False

# init the IndivoClient python object
from indivo_client_py.lib.client import IndivoClient

# todo: safe for now, but revisit this (maybe make a global api object) later
def get_api(request=None):
    api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
    if request:
        api.update_token(request.session['oauth_token_set'])
    
    return api

def tokens_p(request):
    try:
        ########### FIXME CHECK SECURITY ######################
        if request.session['oauth_token_set']:
            return True
        else:
            return False
    except KeyError:
        return False

def tokens_get_from_server(request, username, password):
    """
    This method will not catch exceptions raised by create_session, be sure to catch them!
    """
    # hack! re-initing IndivoClient here
    api = get_api()
    tmp = api.create_session({'username' : username, 'user_pass' : password})
    
    request.session['username'] = username
    request.session['oauth_token_set'] = tmp
    request.session['account_id'] = urllib.unquote(tmp['account_id'])
    
    if DEBUG:
        utils.log('oauth_token: %(oauth_token)s outh_token_secret: %(oauth_token_secret)s' %
                            request.session['oauth_token_set'])
    
    return True

def index(request):
    if tokens_p(request):
        # get the realname here. we already have it in the js account model
        api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
        account_id = urllib.unquote(request.session['oauth_token_set']['account_id'])
        res = api.account_info(account_id = account_id)
        if res and res.response:
            
            # success
            if 200 == res.response.get('response_status', 0):
                e = ET.fromstring(res.response.get('response_data', '<xml/>'))
                fullname = e.findtext('fullName')
                return utils.render_template('ui/index', { 'ACCOUNT_ID': account_id,
                                                             'FULLNAME': fullname,
                                                   'HIDE_GET_MORE_APPS': settings.HIDE_GET_MORE_APPS,
                                                         'HIDE_SHARING': settings.HIDE_SHARING })
            # error
            err_msg = res.response.get('response_data', '500: Unknown Error')
            return utils.render_template(LOGIN_PAGE, {'ERROR': ErrorStr(err_msg), 'RETURN_URL': '/', 'SETTINGS': settings})
            
    return HttpResponseRedirect(reverse(login))
        
def login(request, info=""):
    """
    clear tokens in session, show a login form, get tokens from indivo_server, then redirect to index
    FIXME: make note that account will be disabled after 3 failed logins!!!
    """
    # generate a new session
    request.session.flush()
    
    # set up the template
    FORM_USERNAME = 'username'
    FORM_PASSWORD = 'password'
    FORM_RETURN_URL = 'return_url'
    
    # process form vars
    if request.method == HTTP_METHOD_GET:
        return_url = request.GET.get(FORM_RETURN_URL, '/')
        return utils.render_template(LOGIN_PAGE, {'RETURN_URL': return_url, 'SETTINGS': settings})
    
    if request.method == HTTP_METHOD_POST:
        return_url = request.POST.get(FORM_RETURN_URL, '/')
        if request.POST.has_key(FORM_USERNAME) and request.POST.has_key(FORM_PASSWORD):
            username = request.POST[FORM_USERNAME].lower().strip()
            password = request.POST[FORM_PASSWORD]
        else:
            # Also checked initially in js
            return utils.render_template(LOGIN_PAGE, {'ERROR': ErrorStr('Name or password missing'), 'RETURN_URL': return_url, 'SETTINGS': settings})
    else:
        utils.log('error: bad http request method in login. redirecting to /')
        return HttpResponseRedirect('/')
    
    # get tokens from the backend server and save in this user's django session
    try:
        res = tokens_get_from_server(request, username, password)
    except IOError as e:
        if 403 == e.errno:
            return utils.render_template(LOGIN_PAGE, {'ERROR': ErrorStr('Incorrect credentials'), 'RETURN_URL': return_url, 'SETTINGS': settings})
        if 400 == e.errno:
            return utils.render_template(LOGIN_PAGE, {'ERROR': ErrorStr('Name or password missing'), 'RETURN_URL': return_url, 'SETTINGS': settings})     # checked before; highly unlikely to ever arrive here
        
        err_str = ErrorStr(e.strerror)
        return utils.render_template(LOGIN_PAGE, {'ERROR': err_str, 'RETURN_URL': return_url, 'SETTINGS': settings})
    
    return HttpResponseRedirect(return_url)

def logout(request):
    # todo: have a "you have logged out message"
    request.session.flush()
    return HttpResponseRedirect('/login')


def register(request):
    """
    Returns the register template (GET) or creates a new account (POST)
    """
    if HTTP_METHOD_GET == request.method:
        return utils.render_template('ui/register', {'SETTINGS': settings})
    
    if HTTP_METHOD_POST == request.method:
        if not settings.REGISTRATION.get('enable', False):
            return utils.render_template('ui/error', {'error_message': ErrorStr('Registration disabled'), 'error_status': 403})
        
        # create the account
        post = request.POST
        set_primary = settings.REGISTRATION.get('set_primary_secret', 1)
        user = {    'account_id': post.get('account_id'),
                 'contact_email': post.get('contact_email'),        # this key is not present in the register form
                     'full_name': post.get('full_name'),
              'primary_secret_p': set_primary,
            'secondary_secret_p': settings.REGISTRATION.get('set_secondary_secret', False)}
        api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
        res = api.create_account(user)
        print '-----'
        print 'SENT'
        print user
        print 'RECEIVED'
        print res
        print '-----'
        
        # on success, forward to page according to the secrets that were or were not generated
        if 200 == res.get('response_status', 0):
            account_xml = res.get('response_data', '<root/>')
            account = utils.parse_account_xml(account_xml)
            account_id = account.get('id')
            if not set_primary:
                return utils.render_template(LOGIN_PAGE, {'MESSAGE': _('You have successfully registered. After an administrator has approved your account you may login.'), 'SETTINGS': settings})
            
            return HttpResponseRedirect('/accounts/%s/send_secret/sent' % account_id)
        
        return utils.render_template('ui/register', {'ERROR': ErrorStr(res.get('response_data', 'Setup failed')), 'SETTINGS': settings})


def send_secret(request, account_id, status):
    """
    http://localhost/accounts/[foo@bar.com/]send_secret/[(sent|wrong)]
    """
    if HTTP_METHOD_GET == request.method:
        if account_id:
            if 'wrong' == status:
                return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id, 'ERROR': ErrorStr('Wrong secret')})
            if 'sent' == status:
                return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id, 'MESSAGE': _('Use the link sent to your email address to proceed with account activation')})
        return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id})
    
    if HTTP_METHOD_POST == request.method:
        account_id = request.POST.get('account_id', '')
        if request.POST.get('re_send', False):
            api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
            ret = api.account_secret_resend(account_id=account_id)
            # TODO: Re-send primary secret
            ret = api.account_primary_secret(account_id=account_id)
            print '-----'
            print 'TODO: Emailing the secret is unimplemented. For now printing it here:'
            print ret.response
            print '-----'
            if 404 == ret.response.get('response_status', 0):
                return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id, 'ERROR': ErrorStr('Unknown account')})
            if 200 != ret.response.get('response_status', 0):
                return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id, 'ERROR': ErrorStr('<TODO: Parse status from response>')})
            return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id, 'MESSAGE': _('The activation email has been sent')})
        return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id, 'MESSAGE': _('Use the link sent to your email address to proceed with account activation')})
    return utils.render_template('ui/send_secret', {'ACCOUNT_ID': account_id})


def account_initialization(request, account_id, primary_secret):
    """
    http://localhost/accounts/foo@bar.com/initialize/icmloNHxQrnCQKNn
    Legacy: http://localhost/indivoapi/accounts/foo@bar.com/initialize/icmloNHxQrnCQKNn
    """
    api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
    try_to_init = False
    
    # is this account already initialized?
    ret = api.account_info(account_id=account_id)
    status = ret.response.get('response_status', 500)
    if 404 == status:
        return utils.render_template('ui/error', {'error_status': status, 'error_message': ErrorStr('Unknown account')})
    if 200 != status:
        return utils.render_template('ui/error', {'error_status': status, 'error_message': ErrorStr(ret.response.get('response_data', 'Server Error'))})
    
    account_xml = ret.response.get('response_data', '<root/>')
    account = utils.parse_account_xml(account_xml)
    account_state = account.get('state')
    if 'uninitialized' != account_state:
        if 'active' == account_state:
            return utils.render_template(LOGIN_PAGE, {'MESSAGE': _('This account is active, you may log in below'), 'SETTINGS': settings})
        return utils.render_template(LOGIN_PAGE, {'ERROR': ErrorStr('This account is %s' % account_state), 'SETTINGS': settings})
    
    # bail out if the primary secret is wrong
    has_primary_secret = (len(primary_secret) > 0)      # TODO: Get this information from the server (API missing as of now)
    secondary_secret = ''
    
    if has_primary_secret:
        ret = api.check_account_secrets(account_id=account_id, primary_secret=primary_secret)
        if 200 != ret.response.get('response_status', 0):
            return HttpResponseRedirect('/accounts/%s/send_secret/wrong' % account_id)
    
    # GET the form; if we don't need a secondary secret, continue to the 2nd step automatically
    if request.method == HTTP_METHOD_GET:
        if has_primary_secret:
            # TODO: Use a different call here to check whether a secondary secret is needed
            ret = api.check_account_secrets(account_id=account_id, primary_secret=primary_secret, parameters={'secondary_secret': secondary_secret})
            if 200 == ret.response.get('response_status', 0):
                try_to_init = True
        else:
            return utils.render_template(LOGIN_PAGE, {'MESSAGE': _("You have successfully registered. After an administrator has approved your account you may login."), 'SETTINGS': settings})
    import pdb; pdb.set_trace()
    # POSTed the secondary secret
    if request.method == HTTP_METHOD_POST:
        secondary_secret = request.POST.get('conf1') + request.POST.get('conf2')
        try_to_init = True
    
    # try to initialize
    if try_to_init:
        ret = api.account_initialize(account_id = account_id,
                                 primary_secret = primary_secret,
                                           data = {'secondary_secret': secondary_secret})
        status = ret.response.get('response_status', 0)
        
        if 200 == status:
            return utils.render_template('ui/account_setup', {'FULLNAME': '', 'ACCOUNT_ID': account_id, 'PRIMARY_SECRET': primary_secret, 'SECONDARY_SECRET': secondary_secret, 'settings': settings})
        if 404 == status:
            return utils.render_template(LOGIN_PAGE, {'ERROR': ErrorStr('Unknown account')})
        if 403 == status:
            return utils.render_template('ui/account_init', {'ACCOUNT_ID': account_id, 'PRIMARY_SECRET': primary_secret, 'ERROR': ErrorStr('Wrong confirmation code')})
        
        print '-----'
        print 'account_initialize failed:'
        print ret.response
        print '-----'
        return utils.render_template('ui/account_init', {'ACCOUNT_ID': account_id, 'PRIMARY_SECRET': primary_secret, 'ERROR': ErrorStr('Setup failed')})
    
    return utils.render_template('ui/account_init', {'ACCOUNT_ID': account_id, 'PRIMARY_SECRET': primary_secret})


def account_setup(request, account_id, primary_secret):
    """
    http://localhost/accounts/foo@bar.com/setup/taOFzInlYlDKLbiM
    """
    import pdb; pdb.set_trace()
    if request.method == HTTP_METHOD_POST:
        api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
        
        # get POST data
        post = request.POST
        username = post.get('username', '').lower().strip()
        password = post.get('pw1')
        secondary_secret = post.get('secondary_secret', '')
        has_secondary_secret = (len(secondary_secret) > 0)      # TODO: Get this information from the server (API missing)
        
        # verify the secrets
        params = {}
        if has_secondary_secret:
            params = {'secondary_secret': secondary_secret}
        ret = api.check_account_secrets(account_id=account_id, primary_secret=primary_secret, parameters=params)
        if 200 != ret.response.get('response_status', 0):
            return HttpResponseRedirect('/accounts/%s/send_secret/wrong' % account_id)      # TODO: This assumes primary/both secrets are wrong. Send to "initialize" if only the secondary_secret is wrong
        
        # verify passwords
        error = None
        if len(username) < 1:
            error = ErrorStr("Username too short")
        if len(password) < settings.REGISTRATION.min_password_length:
            error = ErrorStr("Password too short")
        elif password != post.get('pw2'):
            error = ErrorStr("Passwords do not match")
        if error is not None:
            return utils.render_template('ui/account_setup', {'ERROR': error, 'ACCOUNT_ID': account_id, 'PRIMARY_SECRET': primary_secret, 'SECONDARY_SECRET': secondary_secret, 'settings': settings})
        
        # secrets are ok, passwords check out: Attach the login credentials to the account
        ret = api.add_auth_system(
            account_id = account_id,
            data = {
                  'system': 'password',
                'username': username,
                'password': password
            })
        
        if 200 == ret.response['response_status']:
            # everything's OK, log this person in, hard redirect to change location
            try:
                tokens_get_from_server(request, username, password)
            except IOError as e:
                err_msg = ErrorStr(e.strerror)
                return_url = request.POST.get('return_url', '/')
                return utils.render_template(LOGIN_PAGE, {'ERROR': err_msg, 'RETURN_URL': return_url, 'SETTINGS': settings})
            
            return HttpResponseRedirect('/')
        elif 400 == ret.response['response_status']:
             return utils.render_template('ui/account_setup', {'ERROR': ErrorStr('Username already taken'), 'ACCOUNT_ID': account_id, 'PRIMARY_SECRET': primary_secret, 'SECONDARY_SECRET': secondary_secret, 'settings': settings})
        return utils.render_template('ui/account_setup', {'ERROR': ErrorStr('account_init_error'), 'ACCOUNT_ID': account_id, 'PRIMARY_SECRET': primary_secret, 'SECONDARY_SECRET': secondary_secret, 'settings': settings})
    
    # got no secondary_secret, go back to previous step
    return HttpResponseRedirect('/accounts/%s/initialize/%s' % (account_id, primary_secret))


def change_password(request):
    if request.method == HTTP_METHOD_POST:
        account_id = request.POST['account_id']
        old_password = request.POST['oldpw']
        password = request.POST['pw1']
        
        api = get_api(request)
        ret = api.account_change_password(account_id = account_id, data={'old':old_password, 'new':password})
        if ret.response['response_status'] == 200:
            return utils.render_template('ui/change_password_success', {})
        else:
            return utils.render_template('ui/change_password', {'ERROR': ErrorStr('Password change failed'), 'ACCOUNT_ID': account_id})
    else:
        account_id = urllib.unquote(request.session['oauth_token_set']['account_id'])
        return utils.render_template('ui/change_password', {'ACCOUNT_ID': account_id})

def forgot_password(request):
    if request.method == HTTP_METHOD_GET:
        return utils.render_template('ui/forgot_password', {})
    
    if request.method == HTTP_METHOD_POST:
        email = request.POST['email']
        
        api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
        # get account id from email (which we are assuming is contact email)
        ret = api.account_forgot_password(parameters={'contact_email':email})
        
        if ret.response['response_status'] == 200:
            e = ET.fromstring(ret.response['response_data'])
            SECONDARY_SECRET = e.text
            SECONDARY_SECRET_1 = SECONDARY_SECRET[0:3]
            SECONDARY_SECRET_2 = SECONDARY_SECRET[3:6]
            return utils.render_template('ui/forgot_password_2', {'SECONDARY_SECRET_1': SECONDARY_SECRET_1,
                                                                  'SECONDARY_SECRET_2': SECONDARY_SECRET_2})
        else:
            return utils.render_template('ui/forgot_password', {'ERROR': ErrorStr('Password reset failed')})

def forgot_password_2(request):
    account_id = request.path_info.split('/')[2]
    primary_secret = request.path_info.split('/')[3]
    
    if request.method == HTTP_METHOD_GET:
        return utils.render_template('ui/forgot_password_3', {})
    if request.method == HTTP_METHOD_POST:
        secondary_secret = request.POST['conf1'] + request.POST['conf2']
        
        api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
        # check the validity of the primary and secondary secrets
        # http://192.168.1.101/forgot_password_2/jenandfred@verizon.net/GZrggAOLxScQuNAY
        ret = api.check_account_secrets(account_id=account_id, primary_secret=primary_secret, parameters={
            'secondary_secret': secondary_secret
        })
        
        if ret.response['response_status'] == 200:
            return utils.render_template('ui/forgot_password_4', {'ACCOUNT_ID': account_id})
        else:
            return utils.render_template('ui/forgot_password_3', {'ERROR': ErrorStr('Password reset failed')})

def forgot_password_3(request):
    account_id = request.POST['account_id']
    password = request.POST['pw1']
    
    api = IndivoClient(settings.CONSUMER_KEY, settings.CONSUMER_SECRET, settings.INDIVO_SERVER_LOCATION)
    ret = api.account_info(account_id = account_id)
    e = ET.fromstring(ret.response['response_data'])
    username = e.find('authSystem').get('username')
    ret = api.account_set_password(account_id = account_id, data={'password':password})
    
    if ret.response['response_status'] == 200:
        try:
            tokens_get_from_server(request, username, password)
        except IOError as e:
            err_msg = ErrorStr(e.strerror)
            return utils.render_template('ui/forgot_password_3', {'ERROR': err_msg})
        
        return HttpResponseRedirect(reverse(index))
    else:
        return utils.render_template('ui/forgot_password_3', {'ERROR': ErrorStr('Password reset failed')})


def indivo_api_call_get(request):
    """
    take the call, forward it to the Indivo server with oAuth signature using
    the session-stored oAuth tokens
    """
    if DEBUG:
        utils.log('indivo_api_call_get: ' + request.path)
    
    if not tokens_p(request):
        utils.log('indivo_api_call_get: No oauth_token or oauth_token_secret.. sending to login')
        return HttpResponseRedirect('/login')
    
    # update the IndivoClient object with the tokens stored in the django session
    api = get_api(request)
    
    # strip the leading /indivoapi, do API call, and return result
    if request.method == "POST":
        data = dict((k,v) for k,v in request.POST.iteritems())
    else:
        data = {}
    
    return HttpResponse(api.call(request.method, request.path[10:], options= {'data': data}), mimetype="application/xml")

def indivo_api_call_delete_record_app(request):
    """
    sort of like above but for app delete
    """
    if request.method != HTTP_METHOD_POST:
        return HttpResponseRedirect('/')
    
    if DEBUG:
        utils.log('indivo_api_call_delete_record_app: ' + request.path + ' ' + request.POST['app_id'] + ' ' + request.POST['record_id'])
    
    if not tokens_p(request):
        utils.log('indivo_api_call_delete_record_app: No oauth_token or oauth_token_secret.. sending to login')
        return HttpResponseRedirect('/login')
    
    # update the IndivoClient object with the tokens stored in the django session
    api = get_api(request)
    
    # get the app id from the post, and return to main
    status = api.delete_record_app(record_id=request.POST['record_id'],app_id=request.POST['app_id']).response['response_status']
    
    return HttpResponse(str(status))

def authorize(request):
    """
    app_info (the response_data from the get_request_token_info call) looks something like:
    
    <RequestToken token="LNrHRM1OA6ExcSyq22O0">
        <record id="cface90b-6ca0-4368-827a-2ccd5979ffb7"/>
        <carenet />
        <kind>new</kind>
        <App id="indivoconnector@apps.indivo.org">
            <name>Indivo Connector</name>
            <description>None</description>
            <autonomous>True</autonomous>
    
            <autonomousReason>This app connects to your record to load new data into it while you sleep.</autonomousReason>
    
            <frameable>True</frameable>
            <ui>True</ui>
        </App>
    
        <Permissions>
        </Permissions>
    
    </RequestToken>
    """
    if not tokens_p(request):
        url = "%s?return_url=%s" % (reverse(login), urllib.quote(request.get_full_path()))
        return HttpResponseRedirect(url)
    
    api = get_api(request)
    REQUEST_TOKEN = request.REQUEST['oauth_token']
    
    # process GETs (initial adding and a normal call for this app)
    if request.method == HTTP_METHOD_GET and request.GET.has_key('oauth_token'):
        
        # claim request token and check return value
        res = api.claim_request_token(request_token=REQUEST_TOKEN)
        if not res or not res.response:
            return utils.render_template('ui/error', {'error_message': 'no response to claim_request_token'})
        
        response_status = res.response.get('response_status', 500)
        if response_status != 200:
            response_message = res.response.get('response_data', 'bad response to claim_request_token')
            return utils.render_template('ui/error', {'error_status': response_status, 'error_message': ErrorStr(response_message)})
        
        app_info = api.get_request_token_info(request_token=REQUEST_TOKEN).response['response_data']
        e = ET.fromstring(app_info)
        record_id = e.find('record').attrib.get('id', None)
        carenet_id = e.find('carenet').attrib.get('id', None)
        name = e.findtext('App/name')
        app_id = e.find('App').attrib['id']
        kind = e.findtext('kind')
        description = e.findtext('App/description')
        if description == 'None': description = None # remove me after upgrade of template if tags in django 1.2
        autonomous = e.findtext('App/autonomous')
        if autonomous == 'True': 
            autonomous = True
            autonomousReason = e.findtext('App/autonomousReason')
        else:
            autonomous = False
            autonomousReason = ''
        
        # the "kind" param lets us know if this is app setup or a normal call
        if kind == 'new':
            if record_id:
                # single record
                record_xml = api.read_record(record_id = record_id).response['response_data']
                record_node = ET.fromstring(record_xml)
                RECORDS = [[record_node.attrib['id'], record_node.attrib['label']]]
                
                #carenet_els = ET.fromstring(api.get_record_carenets(record_id = record_id).response['response_data']).findall('Carenet')
                #carenets = [{'id': c.attrib['id'], 'name': c.attrib['name']} for c in carenet_els]
                carenets = None
            else:
                records_xml = api.read_records(account_id = urllib.unquote(request.session['account_id'])).response['response_data']
                RECORDS = [[r.get('id'), r.get('label')] for r in ET.fromstring(records_xml).findall('Record')]
                carenets = None
            
            data = {      'app_id': app_id,
                            'name': name,
                           'title': _('Authorize "{{name}}"?').replace('{{name}}', name),
                     'description': description,
                   'request_token': REQUEST_TOKEN,
                         'records': RECORDS,
                        'carenets': carenets,
                      'autonomous': autonomous,
                'autonomousReason': autonomousReason}
            return HttpResponse(simplejson.dumps(data))
            #return utils.render_template('ui/authorize', data)
        elif kind == 'same':
            # return HttpResponse('fixme: kind==same not implimented yet')
            # in this case we will have record_id in the app_info
            return _approve_and_redirect(request, REQUEST_TOKEN, record_id, carenet_id)
        else:
            return utils.render_template('ui/error', {'error_message': 'bad value for kind parameter'})
            #return HttpResponse('bad value for kind parameter')
    
    # process POST
    elif request.method == HTTP_METHOD_POST \
        and request.POST.has_key('oauth_token') \
        and request.POST.has_key('record_id'):
        
        app_info = api.get_request_token_info(request_token=REQUEST_TOKEN).response['response_data']
        e = ET.fromstring(app_info)
        
        record_id = e.find('record').attrib.get('id', None)
        carenet_id = e.find('carenet').attrib.get('id', None)
        name = e.findtext('App/name')
        app_id = e.find('App').attrib['id']
        kind = e.findtext('kind')
        description = e.findtext('App/description')
        
        offline_capable = request.POST.get('offline_capable', False)
        if offline_capable == "0":
            offline_capable = False
        
        location = _approve_and_redirect(request, request.POST['oauth_token'], request.POST['record_id'], offline_capable = offline_capable)
        
        approved_carenet_ids = request.POST.getlist('carenet_id')
        
        # go through the carenets and add the app to the record
        for approved_carenet_id in approved_carenet_ids:
            api.post_carenet_app(carenet_id = approved_carenet_id, app_id = app_id)
        
        return location
    
    return HttpResponse('bad request method or missing param in request to authorize')

def authorize_cancel(request):
    """docstring for authorize_cancel"""
    pass

def _approve_and_redirect(request, request_token, record_id=None, carenet_id=None, offline_capable=False):
    """
    carenet_id is the carenet that an access token is limited to.
    """
    api = get_api(request)
    data = {}
    if record_id:
        data['record_id'] = record_id
    if carenet_id:
        data['carenet_id'] = carenet_id
    
    if offline_capable:
        data['offline'] = 1
    
    result = api.approve_request_token(request_token=request_token, data=data)
    # strip location= (note: has token and verifer)
    location = urllib.unquote(result.response['prd'][9:])
    return HttpResponseRedirect(location)

def localize_jmvc_template(request, *args, **kwargs):
    """
    localize JMVC's .ejs templates using django's template engine
    """
    # get static response
    response = serve(request, *args, **kwargs)
    
    # pass it to the template engine
    response_text = response.content
    template = Template(response_text)
    response_localized = template.render(Context({}))
     
    return HttpResponse(response_localized)
