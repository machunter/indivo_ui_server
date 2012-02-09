/**
 * @tag controllers, home
 * 
 * @author Pascal Pfiffner (pascal.pfiffner@childrens.harvard.edu)
 * @author Arjun Sanyal (arjun.sanyal@childrens.harvard.edu)
 * @author Ben Adida (ben.adida@childrens.harvard.edu)
 *
 */

$.Controller.extend('UI.Controllers.Record',
/* @Static */
{
	
},
/* @Prototype */
{
	init: function() {
		this.account = this.options.account;
		this.alertQueue = this.options.alertQueue;
		
		this.loadRecords();
	},
	
	/**
	 *	Removes all record tabs (but not the add-record tab), fetches the records of this.account, adds tabs for each record and then
	 *	loads the first or the given record.
	 */
	loadRecords: function(load_record) {
		this.removeAllRecordTabs();
		var self = this, 
			colors = ['rgb(250,250,250)', 'rgb(242,246,255)', 'rgb(244,255,242)', 'rgb(250,242,255)', 'rgb(254,255,242)', 'rgb(255,248,242)', 'rgb(255,242,242)', 'rgb(255,242,251)'];
		
		// load records, assign colors and add tabs
		this.account.get_records(function(records) {
			for (var i=0; i< records.length; i++) {
				records[i].bgcolor = colors[i % colors.length];
				self.addTab(records[i]);
			}
			
			// load the desired or first record
			if (records.length > 0) {
				UI.Controllers.MainController.unlockAppSelector();
				var record_to_load = records[0];
				if (load_record) {
					for (var i = 0; i < records.length; i++) {
						if (records[i].id == load_record) {
							record_to_load = records[i];
							break;
						}
					}
				}
				self.loadRecord(record_to_load);
			}
			else {
				UI.Controllers.MainController.showNoRecordsHint();
			}
		},
		function() {
			self.alertQueue.push(new UI.Models.Alert({text:"Sorry, but we were not able to load your records. Please try again later", level:"error"}));
		});
	},

	loadRecord: function(record) {
		var loading_same = (record == this.account.activeRecord);
		var ui_main = $('body').controllers('main')[0];
		if (!ui_main) {
			console.error('There is no main controller on body');
			return;
		}
		this.account.attr("activeRecord", record);
		
		// show/hide carenet owned options
		if (record && record.carenet_id) {
			$('#record_owned_options').hide();
		}
		else if (record) {
			$('#record_owned_options').show();
		}
		
		// show record info if the same record tab was clicked twice
		if (record && loading_same) {
			this.showRecordInfo();
		}
		
		// select the right tab
		ui_main.deselectMainTabs();
		var all_tabs = $('#record_tabs').find('a');
		for (var i = 0; i < all_tabs.length; i++) {
			var tab = $(all_tabs[i]);
			if (record && tab.model() == record) {
				tab.addClass('selected');
			}
			else {
				tab.removeClass('selected');
			}
		}
		
		// set background color to record's color
		if (record) {
			ui_main.tintInterface(record.bgcolor);
		}
	},
	
	".record_tab click": function(el, ev) {
		var record = $(el).model();
		this.loadRecord(record);
		
		// show "create new record" form
		if (!record) {
			this.showRecordForm(el);
		}
	},
	
	/**
	 * Add a record tab
	 */
	addTab: function(record, selected) {
		// TODO: replace with a listener for changes to a List of Records on the Account when JMVC merges Observable into Model
		$('#loading_records_hint').remove();
		// append tab to existing list
		$('#record_tabs').append($.View("//ui/views/record/show_tab", {record:record, selected:selected, color:record ? record.bgcolor : 'rgb(250,250,250)'}));
	},
	
	/**
	 * Remove all but the [+] record tabs
	 */
	removeAllRecordTabs: function() {
		$('#record_tabs .record_tab').not('#add_record_tab').remove();
	},
	
	
	/**
	 *	Show the record overview page
	 */
	showRecordInfo: function() {
		var record = this.account.activeRecord;
		if (!record) {
			console.error('showRecordInfo()', 'Can not show record info page, no activeRecord is set!');
			return;
		}
		
		// deselect apps
		var appListController = $('#app_selector').controller();
		if (appListController) {
			appListController.selectTab(null);
		}
		
		// load template
		var ui_main = $('body').controllers('main')[0];
		if (!ui_main) {
			console.error('There is no main controller attached to body');
			return;
		}
		
		var page = $.View('//ui/views/record/info', {'record': this.account.activeRecord});
		ui_main.tintInterface();
		ui_main.cleanAndShowAppDiv(page);
	},
	
	/**
	 * Show the form to create a new record
	 */
	showRecordForm: function() {
		var ui_main = $('body').controllers('main')[0];
		if (!ui_main) {
			console.error('There is no main controller attached to body');
			return;
		}
		
		var form = $.View('//ui/views/record/create');
		ui_main.tintInterface();
		ui_main.cleanAndShowAppDiv(form);
		$('#givenName').focus();
	},
	
	/**
	 * Did submit the create record form - create a record!
	 * @todo The cancel link does not cancel an active call on a slow network
	 */
	'#new_record_form submit': function(el, ev) {
		el.find('.error_area').first().hide().text('');
		el.find('.loader').first().show();
		$('#create_record_submit').attr('disabled', 'disabled');
		
		// collect data (where's that "form_values" method of jQuery?)
		var dict = {'givenName': el.find('input[name="givenName"]').val(),
				   'familyName': el.find('input[name="familyName"]').val(),
					    'email': el.find('input[name="email"]').val()};
		
		UI.Models.Record.create(dict, this.callback('didCreateNewRecord', el), this.callback('didNotCreateNewRecord', el));
		return false;
	},
	didCreateNewRecord: function(form, data, textStatus, xhr) {
		var new_record_id = null;
		if (data && data.record_id) {
			new_record_id = data.record_id;
		}
		$('#add_record_tab').removeClass('selected');
		this.loadRecords(new_record_id);
	},
	didNotCreateNewRecord: function(form, errXhr) {
		console.log('Error handling not really implemented', errXhr);
		form.find('.error_area').first().text('Error');
		form.find('.loader').first().hide();
		$('#create_record_submit').removeAttr('disabled');
	}
});
