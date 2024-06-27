function datatables_parseHostlink(data, link='') {
	myArr = data.split("___");
	data = '<a class="hostLink" href="' + link +'?host=' + encodeURIComponent(myArr[1]) + '">' + myArr[0] + '</a>';
	return(data);
}

function datatables_parsePlatform(data) {
	if (data == "win") {
		data = '<i class="fab fa-windows fa-2x fa-fw" style="margin-right: 2px; color: rgb(73, 110, 150);" aria-hidden="true"></i>';
	}
	else if (data == "osx") {
		data = '<i class="fab fa-apple fa-2x fa-fw" style="margin-right: 2px; color: rgb(127, 127, 127);" aria-hidden="true"></i>';
	}
	else if (data == "linux") {
		data = '<i class="fab fa-linux fa-2x fa-fw" style="margin-right: 2px;" aria-hidden="true"></i>';
	}
	else {
		data = "N/A"
	}
	return(data);	
}

function datatables_parsePlatformRule(data) {
	if (data == "win") {
		data = '<i class="fab fa-windows fa-lg" style="margin-right: 2px; color: rgb(73, 110, 150);" aria-hidden="true"></i>';
	}
	else if (data == "osx") {
		data = '<i class="fab fa-apple fa-lg" style="margin-right: 2px; color: rgb(127, 127, 127);" aria-hidden="true"></i>';
	}
	else if (data == "linux") {
		data = '<i class="fab fa-linux fa-lg" style="margin-right: 2px;" aria-hidden="true"></i>';
	}
	else {
		data = "N/A"
	}
	return(data);	
}

function host_parsePlatform(data) {
	if (data == "win") {
		data = '<i class="fab fa-windows fa-7x fa-fw" style="margin-right: 2px; color: rgb(73, 110, 150);" aria-hidden="true"></i>';
	}
	else if (data == "osx") {
		data = '<i class="fab fa-apple fa-7x fa-fw" style="margin-right: 2px; color: rgb(127, 127, 127);" aria-hidden="true"></i>';
	}
	else if (data == "linux") {
		data = '<i class="fab fa-linux fa-7x fa-fw" style="margin-right: 2px;" aria-hidden="true"></i>';
	}
	else {
		data = "N/A"
	}
	return(data);	
}

function datatables_parseAcquisitionType(data) {
	if (data == "QUEUED") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-clock fa-md fa-fw' style='margin-right: 2px; color: #840f8e;' aria-hidden='true'></i><b>QUEUED</b>";
		//data += "</span>";
	}
	else if (data == "RUNNING") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-md fa-spin fa-circle-notch' style='margin-right: 2px; color: #d1cd17;' aria-hidden='true'></i><b>RUNNING</b>";
		//data += "</span>";
	}
	else if (data == "COMPLETE") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-check-square fa-md fa-fw' style='margin-right: 2px; color: green;' aria-hidden='true'></i><b>COMPLETE</b>";
		//data += "</span>";
	}
	else if (data == "NEW") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-plus-square fa-md fa-fw' style='margin-right: 2px; color: #f4a742;' aria-hidden='true'></i><b>NEW</b>";
		//data += "</span>";
	}
	else if (data == "STOPPED") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-stop-circle fa-md fa-fw' style='margin-right: 2px; color: #ea475b;' aria-hidden='true'></i><b>STOPPED</b>";
		//data += "</span>";
	}
	else if (data == "ABORTED") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-ban fa-md fa-fw' style='margin-right: 2px; color: #f44242;' aria-hidden='true'></i><b>ABORTED</b>";
		//data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function host_parseAcquisitionType(data) {
	if (data == "triage") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-medkit fa-sm fa-fw' style='margin-right: 2px; color: green;' aria-hidden='true'></i><b>Triage</b>";
		data += "</span>";
	}
	else if (data == "live") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-database fa-sm fa-fw' style='margin-right: 2px; color: #0f468e;' aria-hidden='true'></i><b>Acquisition</b>";
		data += "</span>";
	}
	else if (data == "file") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-file fa-sm fa-fw' style='margin-right: 2px; color: #840f8e;' aria-hidden='true'></i><b>File</b>";
		data += "</span>";
	}
	else if (data == "bulk") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-database fa-sm fa-fw' style='margin-right: 2px; color: #0f468e;' aria-hidden='true'></i><b>Bulk</b>";
		data += "</span>";
	}
	else if (data == "diag") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-diagnoses fa-sm fa-fw' style='margin-right: 2px; color: #0f468e;' aria-hidden='true'></i><b>Diagnostics</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function datatables_parseAcquisitionState(data) {
	if (data == "QUEUED") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-clock fa-lg fa-fw' style='margin-right: 2px; color: #840f8e;' aria-hidden='true'></i>";
		//data += "</span>";
	}
	else if (data == "RUNNING") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-lg fa-spin fa-circle-notch' style='margin-right: 2px; color: #d1cd17;' aria-hidden='true'></i>";
		//data += "</span>";
	}
	else if (data == "COMPLETE") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-check-square fa-lg fa-fw' style='margin-right: 2px; color: green;' aria-hidden='true'></i>";
		//data += "</span>";
	}
	else if (data == "NEW") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-plus-square fa-lg fa-fw' style='margin-right: 2px; color: #f4a742;' aria-hidden='true'></i>";
		//data += "</span>";
	}
	else if (data == "STOPPED") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-stop-circle fa-lg fa-fw' style='margin-right: 2px; color: #ea475b;' aria-hidden='true'></i>";
		//data += "</span>";
	}
	else if (data == "ABORTED") {
		//data = "<span class='htLayoutIconWrapper'>";
		data = "<i class='fas fa-ban fa-lg fa-fw' style='margin-right: 2px; color: #f44242;' aria-hidden='true'></i>";
		//data += "</span>";
	}
	else {
		data = data;
	}
	return(data);	
}

function host_parseAcquisitionState(data) {
	if (data == "QUEUED") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-clock fa-sm fa-fw' style='margin-right: 2px; color: #840f8e;' aria-hidden='true'></i><b>QUEUED</b>";
		data += "</span>";
	}
	else if (data == "RUNNING") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-sm fa-spin fa-circle-notch' style='margin-right: 2px; color: #d1cd17;' aria-hidden='true'></i><b>RUNNING</b>";
		data += "</span>";
	}
	else if (data == "COMPLETE") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-check-square fa-sm fa-fw' style='margin-right: 2px; color: green;' aria-hidden='true'></i><b>COMPLETE</b>";
		data += "</span>";
	}
	else if (data == "NEW") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-plus-square fa-sm fa-fw' style='margin-right: 2px; color: #f4a742;' aria-hidden='true'></i><b>NEW</b>";
		data += "</span>";
	}
	else if (data == "STOPPED") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-stop-circle fa-sm fa-fw' style='margin-right: 2px; color: #ea475b;' aria-hidden='true'></i><b>STOPPED</b>";
		data += "</span>";
	}
	else if (data == "ABORTED") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-ban fa-sm fa-fw' style='margin-right: 2px; color: #f44242;' aria-hidden='true'></i><b>ABORTED</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);	
}

function datatables_parseContainmentState(data) {
	if (data == "normal") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-lock-open fa-md fa-fw' style='margin-right: 2px; color: green;' aria-hidden='true'></i><b>Normal</b>";
		data += "</span>";
	}
	else if (data == "containing") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-unlock fa-md fa-fw' style='margin-right: 2px; color: #cc9216;' aria-hidden='true'></i><b>Containing</b>";
		data += "</span>";
	}
	else if (data == "uncontain") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-unlock fa-md fa-fw' style='margin-right: 2px; color: #cc9216;' aria-hidden='true'></i><b>Uncontain</b>";
		data += "</span>";
	}
	else if (data == "uncontaining") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-unlock fa-md fa-fw' style='margin-right: 2px; color: #cc9216;' aria-hidden='true'></i><b>Uncontaining</b>";
		data += "</span>";
	}
	else if (data == "contain") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-unlock fa-md fa-fw' style='margin-right: 2px; color: #cc9216;' aria-hidden='true'></i><b>Contain</b>";
		data += "</span>";
	}
	else if (data == "contained") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-lock fa-md fa-fw' style='margin-right: 2px; color: #d11717;' aria-hidden='true'></i><b>Contained</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function datatables_parseRuleState(data) {
	if (data == 0) {
		data = "<span class='fe-info--hxtool-icon-warn'>";
		data += "<i class='fas fa-plus fa-md fa-fw' style='margin-right: 2px; color: yellow;' aria-hidden='true'></i><b>new</b>";
		data += "</span>";
	}
	else if (data == 1) {
		data = "<span class='fe-info--hxtool-icon-ok'>";
		data += "<i class='fas fa-check fa-md fa-fw' style='margin-right: 2px; color: green;' aria-hidden='true'></i><b>approved</b>";
		data += "</span>";
	}
	else if (data == 2) {
		data = "<span class='fe-info--hxtool-icon-deny'>";
		data += "<i class='fas fa-ban fa-md fa-fw' style='margin-right: 2px; color: red;' aria-hidden='true'></i><b>deny</b>";
		data += "</span>";
	}
	else if (data == 3) {
		data = "<span class='fe-info--hxtool-icon-ok'>";
		data += "<i class='fas fa-check-square fa-md fa-fw' style='margin-right: 2px; color: green;' aria-hidden='true'></i><b>submitted</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function datatables_parseSource(data) {
	if (data == "IOC") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-link fa-md fa-fw' style='margin-right: 2px; color: #001ee5;' aria-hidden='true'></i><b>IOC</b>";
		data += "</span>";
	}
	else if (data == "EXD") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-file-code fa-md fa-fw' style='margin-right: 2px; color: #e50700;' aria-hidden='true'></i><b>EXG</b>";
		data += "</span>";
	}
	else if (data == "MAL") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-bug fa-md fa-fw' style='margin-right: 2px; color: #f4a742;' aria-hidden='true'></i><b>MAL</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function host_parseSource(data) {
	if (data == "IOC") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-link fa-sm fa-fw' style='margin-right: 2px; color: #001ee5;' aria-hidden='true'></i><b>IOC</b>";
		data += "</span>";
	}
	else if (data == "EXD") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-file-code fa-sm fa-fw' style='margin-right: 2px; color: #e50700;' aria-hidden='true'></i><b>EXG</b>";
		data += "</span>";
	}
	else if (data == "MAL") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-bug fa-sm fa-fw' style='margin-right: 2px; color: #f4a742;' aria-hidden='true'></i><b>MAL</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function datatables_parseResolution(data) {
	if (data == "ALERT") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-exclamation-circle fa-md fa-fw' style='margin-right: 2px; color: #f4a742;' aria-hidden='true'></i><b>ALERT</b>";
		data += "</span>";
	}
	else if (data == "BLOCK") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-stop-circle fa-md fa-fw' style='margin-right: 2px; color: #e50700;' aria-hidden='true'></i><b>BLOCK</b>";
		data += "</span>"
	}
	else if (data == "QUARANTINED") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-database fa-md fa-fw' style='margin-right: 2px; color: #e50700;' aria-hidden='true'></i><b>QUARANTINE</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function host_parseResolution(data) {
	if (data == "ALERT") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-exclamation-circle fa-sm fa-fw' style='margin-right: 2px; color: #f4a742;' aria-hidden='true'></i><b>ALERT</b>";
		data += "</span>";
	}
	else if (data == "BLOCK") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-stop-circle fa-sm fa-fw' style='margin-right: 2px; color: #e50700;' aria-hidden='true'></i><b>BLOCK</b>";
		data += "</span>"
	}
	else if (data == "QUARANTINED") {
		data = "<span class='htLayoutIconWrapper'>";
		data += "<i class='fas fa-database fa-sm fa-fw' style='margin-right: 2px; color: #e50700;' aria-hidden='true'></i><b>QUARANTINE</b>";
		data += "</span>";
	}
	else {
		data = data;
	}
	return(data);
}

function datatables_alertTimestamps(data, matched_at, reported_at) {

	element = "<span class='hostLink alerttimestamp'>" + data.replace("T", " ").substring(0,19) + "</span>";
	element += "<div class='fe-panel__body' style='margin-left: 10px; margin-top: 5px; padding: 10px; display: none; position: absolute; border: 1px solid rgba(15, 184, 220, 0.4)'>";
	element += "Matched at: " + matched_at.replace("T", " ").substring(0,19) + "<br>"
	element += "Reported at: " + reported_at.replace("T", " ").substring(0,19)
	element += "</div>"

	return(element);
}

function datatables_Timestamp(data) {
	return(data.replace("T", " ").substring(0,19));
}

