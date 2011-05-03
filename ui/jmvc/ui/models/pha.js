/**
 * @tag models, home
 * 
 * @author Arjun Sanyal (arjun.sanyal@childrens.harvard.edu)
 * @author Ben Adida (ben.adida@childrens.harvard.edu)
 *
 */
$.Model.extend('UI.Models.PHA',
/* @Static */
{
  single_callback: function(callback) {
    var ajax_callback = function(result) {
      var pha = result.App;
      callback(new UI.Models.PHA({'id': pha['@id'], 'data': pha}));
    };
    return ajax_callback;
  },

  multi_callback: function(callback) {
    ajax_callback = function(result) {
      var pha_list = result.Apps;
      if (pha_list == null) {
        callback([]);
        return;
      }

      var phas = pha_list.App;

      // for consistency
      if (!(phas instanceof Array)) { phas = [phas]; }
      
      var pha_objs = $(phas).map(function(i, pha) { return new UI.Models.PHA({'id': pha['@id'], 'data': pha}); });
      callback(pha_objs);
    };
    return ajax_callback;
  },

  get_by_record: function(record_id, type, callback) {
    var url = '/records/' + encodeURIComponent(record_id) + '/apps/';
    if (type) { url += "?type=" + encodeURIComponent(type); }
    $.getXML(url, this.multi_callback(callback));
  },

  get_by_carenet: function(carenet_id, type, callback) {
    var url = '/carenets/' + encodeURIComponent(carenet_id) + '/apps/';
    if (type) { url += "?type=" + encodeURIComponent(type); }
    $.getXML(url, this.multi_callback(callback));
  },

  get_all: function(callback) { $.getXML('/apps/', this.multi_callback(callback)); },

  get: function(record_id, pha_id, callback) {
    var url = '/records/' + encodeURIComponent(record_id) + '/apps/' + encodeURIComponent(pha_id);
    $.getXML(url, this.single_callback(callback));
  },
  
  delete_pha: function(record_id, pha_id, callback) {
    indivo_api_call('delete',
                    '/records/' + encodeURIComponent(record_id) + '/apps/' + encodeURIComponent(pha_id),
                    {},
                    callback);
    }
},

/* 
  @Prototype 

  magic attrs:
  id,
  data
  data.framable
  data.ui
*/
{
    // These pertain mostly to SMART right now
    add_to_record: function(record_id, callback) {
	// FIXME: we'll want some kind of authorize screen first
	if (this.type == "smart") {
	    indivo_api_call("POST", "/smart/records/" + record_id + "/apps/"+ this.id + "/setup",
			    null, function(result) {
				callback();
			    },
			    function(error) {
				alert('oy adding smart app');
			    });
	    
	    return;
	}

	// if we haven't matched a type, just call the callback
	callback();
    },

    remove_from_record: function(record_id, callback) {
	// for now, smart only
	// FIXME: we'll want some kind of authorize screen first
	if (this.type == "smart") {
	    indivo_api_call("POST", "/smart/records/" + record_id + "/apps/"+ this.id + "/remove",
			    null, function(result) {
				callback();
			    },
			    function(error) {
				alert('oy removing smart app');
			    });
	    
	    return;
	}
	
	// if we haven't matched a type, just call the callback
	callback();
    }
    
})