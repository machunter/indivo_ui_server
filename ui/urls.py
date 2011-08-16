from django.conf.urls.defaults import *
from django.conf import settings
from ui.views import *
from widget_views import *

# maps url patterns to methods in views.py
urlpatterns = patterns(
    '',
    # testing
    (r'^$', index),

    # auth
    (r'^login$', login),
    (r'^logout$', logout),
    (r'^register$', register),
    (r'^change_password$', change_password),
    (r'^forgot_password$', forgot_password),
    (r'^forgot_password_2.*$', forgot_password_2),
    (r'^forgot_password_3$', forgot_password_3),

    # account init emails
    # http://localhost/init/catherine800@indivohealth.org/icmloNHxQrnCQKNn
    # Legacy: http://localhost/indivoapi/accounts/catherine800@indivohealth.org/initialize/icmloNHxQrnCQKNn
    (r'^accounts/send_secret', send_secret, {'account_id': '', 'status': None}),
    (r'^accounts/(?P<account_id>[^/]+)/send_secret$', send_secret, {'status': None}),
    (r'^accounts/(?P<account_id>[^/]+)/send_secret/(?P<status>[^/]*)', send_secret),
    (r'^accounts/(?P<account_id>[^/]*)/initialize/(?P<primary_secret>[^/]*)', account_initialization),
    (r'^indivoapi/accounts/(?P<account_id>[^/]*)/initialize/(?P<primary_secret>[^/]*)', account_initialization),        # legacy support, is this still needed?
    (r'^accounts/(?P<account_id>[^/]*)/setup/(?P<primary_secret>[^/]*)', account_setup),
    (r'^indivoapi/accounts/(?P<account_id>[^/]*)/initialize/account_initialization_2', account_setup),                  # legacy support, is this still needed?

    # indivo api calls
    (r'^indivoapi/delete_record_app/$', indivo_api_call_delete_record_app),
    (r'^indivoapi/', indivo_api_call_get),

    # oauth
    (r'^oauth/authorize$', authorize),

    # widgets
    (r'^lib/(?P<path>[^/]*)$', 'django.views.static.serve', {'document_root': settings.SERVER_ROOT_DIR + '/ui/lib'}),
    (r'^widgets/DocumentAccess$', document_access),

    # this could be improved: we could provide shortcuts for things like css, js, etc for less
    # verbose paths in templates, etc., but for now let's keep things very literal
    # for instance:
    # <script type="text/javascript" src="/jmvc/ui/resources/js/jquery-x.js"></script>
    # could be
    # "/js/jquery-x.js" -> /jmvc/ui/resources/js/jquery-x.js

    # This servers JMVC view templates, but passes them trough django's template engine.
    # This allows localization with standart django template tags - trangs, blocktrans
    (r'^jmvc/(?P<path>.*ejs)$', localize_jmvc_template, {'document_root': settings.SERVER_ROOT_DIR + '/ui/jmvc/'}),
    (r'^jmvc/(?P<path>ui/controllers/.*js)$', localize_jmvc_template, {'document_root': settings.SERVER_ROOT_DIR + '/ui/jmvc/'}),
    
    # this just prepends /ui/ to and /jmvc/ path so that we can ignore the django dir structure
    (r'^jmvc/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.SERVER_ROOT_DIR + '/ui/jmvc/'}),
)
