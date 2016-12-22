/*
So there's load of code here that could be stripped out by using Angular/React/Whevs.
For my purposes, simple JQuery suits me just fine but this really looks like a job for React

The way this is written is BRITTLE so should be refactored if it goes anywhere other than a demo

TODO: Add alerts when ajax calls fail

 */

var flashes = {};


function handleAjaxError(jqXHR, textStatus, errorThrown) {
    bootbox.alert("Bad status from backend: " + jqXHR.status + ', ' + jqXHR.responseText);
}

function upsertRow(checked, currency, amount) {
    var existingRow = $('tbody.required-trades tr.currency-'+currency);
    var currencyTotal = existingRow.find('td.trade-amount');

    if (checked) {
        if (existingRow.length == 0) {
            /* Insert new invoiceLine for currency */
            $("tbody.required-trades").append('<tr class="currency-' + currency + '"><td class="trade-currency">' + currency + '</td>' +
                '<td class="trade-amount">' + parseFloat(amount).toFixed(2) + '</td>/tr>' +
                '<td class="gbp"></td>' +
                '<td class="quoted-rate"></td>' +
                '<td class="quote-id" hidden></td>');

        } else {
            /* Row already exists */
            currencyTotal.text(parseFloat(parseFloat(amount) + parseFloat(currencyTotal.text())).toFixed(2));

        }
    } else {
        var newTotal = parseFloat(parseFloat(currencyTotal.text()) - parseFloat(amount)).toFixed(2);

        if (newTotal == 0) {
            /* Ditch the trade sum total as no longer required */
            existingRow.remove();
        } else {
            currencyTotal.text(newTotal);
        }
    }
}

$('input[type=checkbox]').change(
    function() {
        var invoiceLine = $(this).parent().parent();
        upsertRow(this.checked, invoiceLine.find("td.currency-code").text(), invoiceLine.find("td.bill-amount").text());

        if ($('tbody.required-trades tr').length > 0)
            $('div.quotes-button-wrapper').show();

        else
            $('div.quotes-button-wrapper').hide();
    }
);

/* When Get Quotes clicked call out to API */
$('.get-quotes').click(
  function () {
    $('tbody.required-trades tr').each(function () {
        var amount = $(this).find('td.trade-amount').text();
        var currency = $(this).find('td.trade-currency').text();

        var currentRow = this;

        $.ajax({
            url: 'quote',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ sell: "GBP", buy: currency, amount: amount}),
            success: function(data, textStatus, xhr) {
                    // console.log(data);

                    var quote_value = $(currentRow).find('td.quoted-rate');
                    var sell_amount = $(currentRow).find('td.gbp');
                    var quote_id = $(currentRow).find('td.quote-id');

                    quote_value.text(data.quoted_rate);
                    sell_amount.text(data.sell_amount);
                    quote_id.text(data.quote_id);
                    quote_value.css({'color': 'black'});
                    $('.get-quotes').prop('disabled', true);

                    flashes[currency] = setInterval(flashOnce.bind(quote_value, quote_value), 2000);
                    setTimeout(stopFlashing.bind(currency, currency, quote_value, quote_value, sell_amount, sell_amount, false, false), 25000);
                    $('div.trades-button-wrapper').show();
            },
            error: handleAjaxError
        });
    });
  }
);


$('.book-trade').click(
    function() {
        $('tbody.required-trades tr').each(function () {
            var currentRow = this;
            var contactIds = [];

            $('tbody.invoice-lines tr').each(function () {
                if ($(currentRow).find('td.trade-currency').text() == $(this).find('td.currency-code').text() &&
                    $(this).find('td.checkbox-td>input:checkbox')[0].checked) {

                    contactIds.push({
                        contact_id: $(this).find('td.contact-id').text(),
                        invoice_id: $(this).find('td.invoice-id').text(),
                        amount: $(this).find('td.bill-amount').text()
                    });
                }
            });

            /* OK sending in details to be sent back again is sheer laziness, but easiest way to correlate the data
               effectively */
            $.ajax({
                url: 'trade',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    quote_id: $(currentRow).find('td.quote-id').text(),
                    currency: $(currentRow).find('td.trade-currency').text(),
                    rate: $(currentRow).find('td.quoted-rate').text(),
                    contacts: contactIds
                }),
                success: function(data, textStatus, xhr) {
                    // console.log(data);
                    stopFlashing($(currentRow).find('td.trade-currency').text(),
                        $(currentRow).find('td.quoted-rate'),
                        $(currentRow).find('td.gbp'),
                        true);
                    populateBeneficiaries(data.contacts);

                },
                error: handleAjaxError

            });
    })
        $(this).prop('disabled', true);

});

function flashOnce(quote_value) {
    quote_value.fadeIn(500).fadeOut(500);
}

function stopFlashing(currency, quote_value, sell_amount, trade_booked) {
    // Trash the interval
    clearInterval(flashes[currency]);
    delete flashes[currency];

    if (trade_booked === true) {
        quote_value.fadeIn(500);
        quote_value.css({'color': 'green'});


    } else if (quote_value.css('color') != 'rgb(0, 128, 0)') {
        console.log(quote_value.css('color'));

        // Change button state
        $('div.trades-button-wrapper').hide();
        $('.get-quotes').prop('disabled', false);

        // Set values
        sell_amount.text('Expired');
        quote_value.fadeIn(500);
        quote_value.text('Expired');
        quote_value.css({'color': 'red'});
    }
}

function populateBeneficiaries(contactInfo) {
    // Spit out contact details to Beneficiaries table, then display (table is editable...)
    console.log(contactInfo);

    for (var i = 0; i < contactInfo.length; i++) {
        $("tbody.beneficiaries").append('<tr>' +
                '<td hidden class="xero_contact_id">' + contactInfo[i].xero_contact_id + '</td>' +
                '<td hidden class="ebury_beneficiary_id">' + contactInfo[i].ebury_beneficiary_id + '</td>' +
                '<td hidden class="account_id">' + contactInfo[i].account_id + '</td>' +
                '<td hidden class="invoice_id">' + contactInfo[i].invoice_id + '</td>' +
                '<td hidden class="trade_id">' + contactInfo[i].trade_id + '</td>' +
                '<td hidden class="currency">' + contactInfo[i].currency + '</td>' +
                '<td hidden class="amount">' + contactInfo[i].amount + '</td>' +
                '<td hidden class="rate">' + contactInfo[i].rate + '</td>' +
                '<td class="name">' + contactInfo[i].name + '</td>' +
                '<td class="country_code">' + contactInfo[i].country_code + '</td>' +
                '<td class="account_name">' + contactInfo[i].account_name + '</td>' +
                '<td class="bank_country_code">' + contactInfo[i].bank_country_code + '</td>' +
                '<td class="bank_currency_code">' + contactInfo[i].bank_currency_code + '</td>' +
                '<td class="account_number">' + contactInfo[i].account_number + '</td>' +
                '<td class="iban">' + contactInfo[i].iban + '</td>' +
                '<td class="swift_code">' + contactInfo[i].swift_code + '</td>' +
            '</tr>'
        );
    }
    $('.beneficiaries-row').show();
    $('.target-beneficiaries').editableTableWidget();

    $('.target-beneficiaries td').on('change', function(evt, newValue) {
	    // do something with the new cell value
	    if (this.className in ['currency', 'amount', 'rate']) {
		    return false; // reject change
	    }
    });
}

$('.provision-beneficiaries').click(
    function() {
        var beneficiaries = [];

        // Loop through table and grab values
        $("tbody.beneficiaries tr").each(function () {
            var beneficiary = {}

            for (var i = 0, col; col = this.cells[i]; i++) {
                beneficiary[col.className] = col.innerHTML;
            }

            beneficiaries.push(beneficiary);
        });

        $.ajax({
            url: 'pay',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(beneficiaries),
            success: function(data, textStatus, xhr) {
                console.log(data);
                location.reload();
            },
            error: handleAjaxError
        });
    }
);