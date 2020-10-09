Btn=('<span class="input-group-btn"></span>\
        <span class="btn-file btn primary-button">\
        Agregar archivo pdf &hellip; <input type="file" id="fileupload" name="file" multiple>\
    </span>');
$(function(){
    GetWishes(1);
    $('#BtnFile').html(Btn);

    $('#fileupload').fileupload({
        url: "/AddPdf",
        dataType: 'json',
        add: function (e, data) {
            data.submit();
            $('#Load2').modal();
            $('#BtnFile').empty();
        },
        success: function(responce){
            console.log(responce);
            if (responce.status == 'OK'){
                GetWishes(1);
                $('#Table1').empty();
                $('#Table1').html(responce.principalInfo);
                $('#Table2').empty();
                $('#Table2').html(responce.secondaryInfo);
                $('#AddedPDF').modal();
                $('#BtnFileLabel').empty();
                $('#BtnFileLabel').html('Para cargar otro archivo recargue ó refresque la pagina');
            }
            else if (responce.status == 'NotFoundMaterials'){
                UrlRoot = window.location.href.replace("/ShowAddPackingListInfo","");
                var url=UrlRoot+'/ShowMaterialsNotFound/'+responce.NumTest;
                window.open(url, "List").focus();
                console.log('url: '+url);
                setTimeout('window.location="../ShowAddPackingListInfo"',10000);
            }
            else{
                $('#msjalert').empty();
                $('#msjalert').html(responce.status);
                $('#warning').modal();
                setTimeout('window.location="../ShowAddPackingListInfo"',10000);
            }

        },
        error:function(error){
            console.log(error['responseText']);
            $('#msjalert').empty();
            $('#msjalert').html(error['responseText']);
            $('#Load2').modal('hide');
            $('#warning').modal();
            setTimeout('window.location="../ShowAddPackingListInfo"',10000);
        }
    });

    $('#btnDelete').click(function() {
        $.ajax({
            url: '/DeletedPackingListInfo',
            data: {Id: $('#deleteid').val(),},
            type: 'POST',
            success: function(res) {
                var result = JSON.parse(res);
                if (result.status == 'OK'){
                    $('#DeleteModal').modal('hide');
                    GetWishes(1);
                    $('#msjok').empty();
                    $('#msjok').html('Registro Eliminado');
                    $('#succes').modal();
                }else{
                    $('#DeleteModal').modal('hide');
                    $('#msjalert').empty();
                    $('#msjalert').html(result.status);
                    $('#warning').modal();
                }
            },
            error: function(error) {
                $('#DeleteModal').modal('hide');
                $('#msjdanger').empty();
                $('#danger').modal();
                $('#msjdanger').html(error);
            }
        })
    });

    $('#btnUpdate').click(function() {
        if ($("#updatefecha").val() == ""
        || $("#updatepeso").val() == ""
        || $("#updatevolumen").val() == ""
        || $("#updateunidades").val() == "" ){
            alert ("Llenar todos los campos");
        }
        else if ( $("#updatepeso").val() < .001
        || $("#updatevolumen").val() < .001
        || $("#updateunidades").val() < 1 ){
            alert ("Verificar los valores en Peso, Volumen o Unidades los valores no pueden ser negativos o 0");
        }
        else{
            $.ajax({
                url: '/UpdatePackingListInfo',
                data: {
                    Id: $('#idDoc').val(),
                    Fecha: $('#updatefecha').val(),
                    Peso: $('#updatepeso').val(),
                    Volumen: $('#updatevolumen').val(),
                    Unidades: $('#updateunidades').val(),
                },
                type: 'POST',
                success: function(res) {
                    var result = JSON.parse(res);
                    if (result.status == 'OK'){
                        $('#editModal').modal('hide');
                        GetWishes(1);
                        $('#msjok').empty();
                        $('#msjok').html('Registro Actualizado');
                        $('#succes').modal();
                    }else{
                        $('#editModal').modal('hide');
                        $('#msjalert').empty();
                        $('#msjalert').html(result.status);
                        $('#warning').modal();
                    }
                },
                error: function(error) {
                    $('#editModal').modal('hide');
                    $('#msjdanger').empty();
                    $('#msjdanger').html(error);
                    $('#danger').modal();
                }
            })
        }
    });

    $('#btnStart').click(function() {
        $.ajax({
            url: '/StartPackingLabeling',
            data: {packingId: $('#startid').val(),},
            type: 'POST',
            success: function(res) {
                var result = JSON.parse(res);
                if (result.status == 'OK'){
                    $('#StartTaggingModal').modal('hide');
                    GetWishes(1);
                    $('#msjok').empty();
                    $('#msjok').html('Etiquetado Iniciado');
                    $('#succes').modal();
                }else{
                    $('#StartTaggingModal').modal('hide');
                    $('#msjalert').empty();
                    $('#msjalert').html(result.status);
                    $('#warning').modal();
                }
            },
            error: function(error) {
                $('#StartTaggingModal').modal('hide');
                $('#msjdanger').empty();
                $('#danger').modal();
                $('#msjdanger').html(error);
            }
        })
    });

});

function AddPrincipalInfo(){
    var minDate = Date.parse("2018-01-01");
    var InputDate = Date.parse($("#fecha").val());
    if (   $("#transporte").val() == ""
        || $("#fecha").val() == ""
        || $("#peso").val() == ""
        || $("#volumen").val() == ""
        || $("#unidades").val() == "" ){
            return false;
    }
    else if ( $("#peso").val() < .001
    || $("#volumen").val() < .001
    || $("#unidades").val() < 1
    || InputDate < minDate ){
        return false;
    }
    else{
        $.ajax({
            url: '/AddPackingListInfo',
            data: {
                Transporte: $('#transporte').val(),
                Fecha: $('#fecha').val(),
                Peso: $('#peso').val(),
                Volumen: $('#volumen').val(),
                Unidades: $('#unidades').val()
            },
            type: 'POST',
            success: function(res) {
                var result = JSON.parse(res);
                if (result.status == 'OK'){
                    GetWishes(1);
                    $("#transporte").val("");
                    $("#fecha").val("");
                    $("#peso").val("");
                    $("#volumen").val("");
                    $("#unidades").val("");
                    $('#msjok').empty();
                    $('#msjok').html("Registro agregado");
                    $('#succes').modal();
                }
                else{
                    $('#msjalert').empty();
                    $('#msjalert').html(result.status);
                    $('#warning').modal();
                }
            },
            error: function(error) {
                $('#msjdanger').empty();
                $('#danger').modal();
                $('#msjdanger').html(error);
            }
        });
    }
}

function mySubmitFunction(e) {
    e.preventDefault();
    return false;
}

function GetWishes(_page){
    var _offset = (_page - 1) * 25;
    $.ajax({
        url : '/GetAllsPackingListInfo',
        type : 'POST',
        data : {
            offset:_offset,
            limit:25
        },
        success: function(res){
            var itemsPerPage = 25;
            var wishObj = JSON.parse(res);
            $('#ulist').empty();
            $('#listTemplate').tmpl(wishObj[0]).appendTo('#ulist');
            var total = wishObj[1]['total'];
            var pageCount = total/itemsPerPage;
            var pageRem = total%itemsPerPage;
            if(pageRem !=0 ){
                pageCount = Math.floor(pageCount)+1;
            }
            $('.pagination').empty();
            var pageStart = $('#hdnStart').val();
            var pageEnd = $('#hdnEnd').val();
            if(pageStart>5){
                var aPrev = $('<a/>').attr({'href':'#'},{'aria-label':'Previous'})
                .append($('<span/>').attr('aria-hidden','true').html('&laquo;'));
                $(aPrev).click(function(){
                    $('#hdnStart').val(Number(pageStart) - 5);
                    $('#hdnEnd').val(Number(pageStart) - 5 + 4);
                    GetWishes(Number(pageStart) - 5);
                });
                var prevLink = $('<li/>').append(aPrev);
                $('.pagination').append(prevLink);
            }
            for(var i=Number(pageStart);i<=Number(pageEnd);i++){
                if (i > pageCount){ break; }
                var aPage = $('<a/>').attr('href','#').text(i);
                $(aPage).click(function(i){ return function(){ GetWishes(i); } }(i));
                var page = $('<li/>').append(aPage);
                if((_page)==i){ $(page).attr('class','active'); }
                $('.pagination').append(page);
            }
            if ((Number(pageStart) + 5) <= pageCount){
                var nextLink = $('<li/>').append($('<a/>').attr({'href':'#'},{'aria-label':'Next'})
                .append($('<span/>').attr('aria-hidden','true').html('&raquo;').click(function(){
                    $('#hdnStart').val(Number(pageStart) + 5);
                    $('#hdnEnd').val(Number(pageStart) + 5 + 4);
                    GetWishes(Number(pageStart) + 5);
                })));
                $('.pagination').append(nextLink);
            }
        },
        error: function(error){
            $('#msjdanger').empty();
            $('#danger').modal();
            $('#msjdanger').html(error);
            console.log(error);
        }
    });
}

function Edit(elm) {
    $('#idDoc').val($(elm).attr('data-id'));
    $('#updatetransporte').val($(elm).attr('data-Transport'));
    $('#updatefecha').val($(elm).attr('data-Date'));
    $('#updatepeso').val($(elm).attr('data-Qty'));
    $('#updatevolumen').val($(elm).attr('data-Vol'));
    $('#updateunidades').val($(elm).attr('data-Units'));
    $('#editModal').modal();
}

function Delete(elm) {
    $('#deleteid').val($(elm).attr('data-id'));
    $('#DeleteModal').modal();
}

function StartTagging(elm){
    $("#startid").val($(elm).attr('data-id'));
    msg=("¿Esta seguro de empezar con el etiquetado \
    del packing list No. Documento: "+$(elm).attr('data-Transport')+" ? \
    <br> \
    Al realizar esta acción ya no podremos editar la información principal \
    ni la información de sus bultos documentados o eliminar el packing list.\
    <br> si deseas realizar esta acción dar click en el botón\
    <label style='color:#2ECC71;font-size: 25px;'>Aceptar.</label>\
    <br>de lo contrario dar click en el botón\
    <label style='color:#285078;font-size: 25px;'>cancelar</label>")
    $("#MsgStart").empty();
    $("#MsgStart").html(msg);
    $("#StartTaggingModal").modal();
}

function GetIdFile(elm) {
    $('#filexlsx').fileupload({
        url: "/AddXlsx",
        dataType: 'json',
        add: function (e, data) {
            data.submit();
            $('#Load2').modal();
        },
        success: function(responce){
            console.log(responce);
            if (responce.status == 'OK'){
                AddReferencesToPackigViaXlsxFile(elm);
            }
            else{
                $('#msjalert').empty();
                $('#msjalert').html(responce.status);
                $('#warning').modal();
                setTimeout('window.location="../ShowAddPackingListInfo"',10000);
            }
        },
        error:function(error){
            console.log(error['responseText']);
            $('#msjalert').empty();
            $('#msjalert').html(error['responseText']);
            $('#Load2').modal('hide');
            $('#warning').modal();
            setTimeout('window.location="../ShowAddPackingListInfo"',10000);
        }
    });
}


function AddReferencesToPackigViaXlsxFile(elm){
    $.ajax({
        url: '/AddReferencesToPackigViaXlsxFile',
        data: {
            Id: $(elm).attr('data-Id'),
            Packing: $(elm).attr('data-Packing'),
        },
        type: 'POST',
        success: function(res) {
            var result = JSON.parse(res);
            if (result.status == 'OK'){
                
            }
            else if (result.status == 'NotFoundMaterials'){
                UrlRoot = window.location.href.replace("/ShowAddPackingListInfo","");
                var url=UrlRoot+'/ShowMaterialsNotFound/'+responce.NumTest;
                window.open(url, "List").focus();
                console.log('url: '+url);
                setTimeout('window.location="../ShowAddPackingListInfo"',10000);
            }
            else{
                $('#msjalert').empty();
                $('#msjalert').html(result.status);
                $('#warning').modal();
            }
        },
        error: function(error) {
            $('#msjdanger').empty();
            $('#danger').modal();
            $('#msjdanger').html(error);
        }
    });
}