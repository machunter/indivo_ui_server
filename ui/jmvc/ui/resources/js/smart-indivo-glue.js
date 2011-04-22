/*
 * Glue between SMArt and Indivo
 * 
 * Ben Adida (updated 2011-03-25)
 */

SMART_HELPER  = {};
SMART_HELPER.tokens_by_app= {};

SMART_HELPER.handle_record_info = function(activity, callback) {
    var current_record = RecordController.RECORDS[RecordController.RECORD_ID];
    callback({
	'user' : {
	    'id': ACCOUNT.account_id,
	    'full_name' : ACCOUNT.username
	},
	'record' : {
	    'full_name' : current_record.label,
	    'id' : current_record.record_id
	},
	'credentials': {
	    // for SMART REST, need to generate tokens and put them in here.
	}
    });
};

SMART_HELPER.handle_api = function(activity, message, callback) {
    // should we do something different based on activity? Probably

    if (api_call.method == "GET" && api_call.func == "/capabilities/") {
	callback("<?xml version='1.0'?><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'></rdf:RDF>");
    }


    $.ajax({
	    url: "/indivoapi/smart"+message.func,
	    data: message.params,
	    type: "GET",
	    dataType: "text",
	    success: callback,
	    error: function(data) {
		alert("error");
	    }
	});
};

SMART_HELPER.handle_resume_activity = function(activity, callback) {
	OpenAjax.hub.publish("request_visible_element",  $(activity.iframe));
	callback();
};


SMART_HELPER.handle_start_activity = function(activity, callback) {
    var account_id_enc = encodeURIComponent(ACCOUNT.account_id);
    var record_id_enc = encodeURIComponent(RecordController.RECORD_ID);
    var app_email_enc = encodeURIComponent(activity.app);

    var iframe = $('#app_content_iframe')[0];

    // temporarily FIXME HACK
    callback(iframe);
    return;

    $.ajax({
	    url: "/smart/accounts/"+account_id_enc+"/apps/"+app_email_enc+"/records/"+record_id_enc+"/launch",
		data: null,
		type: "POST",
		dataType: "text",
		success: 
	    function(data) {
		d  = MVC.Tree.parseXML(data);    				
		if (d.AccessToken.App["@id"] !== app_email)
		    throw "Got back access tokens for a different app! " + app_email +  " vs. " + d.AccessToken.App["@id"];
		SMART_HELPER.tokens_by_app[app_email] = {token:d.AccessToken.Token, secret: d.AccessToken.Secret};
		callback(iframe);
	    },
		error: function(data) {
		// error handler
		err = data;
		alert("error fetching token xml " + data);
	    }
    	});    		
};

