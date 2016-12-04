function updateAverageRating(msg) {
    if (msg.ratingFrequency == 0)
        $("#average-rating-section").css("display", "none");
        
    else {
        $("#average-rating-section").css("display", "inline");
        $("#rating-frequency").text(msg.ratingFrequency);
        $("#average-rating").text(msg.ratingAverage.toFixed(1));
        $("#user-demonym").text(msg.ratingFrequency == 1 ? "user" : "users");
    }
}

function rateRelease(clicked_element, release_id, rating) {
    /*User clicked the already selected rating
       => unrate*/
    var unrating = clicked_element.classList.contains("selected");
    
    $.ajax({
        method: "POST",
        url: "/release/" + release_id,
        data: {action: unrating ? "unrate" : "rate", rating: rating}
        
    }).done(function (msg) {
        if (msg.error)
            return;
            
        /*Success, update rating widget*/
        
        if (unrating)
            clicked_element.classList.remove("selected");
        
        else {
            var siblings = clicked_element.parentNode.children;
            
            for (var i = 0; i < siblings.length; i++)
                siblings[i].classList.remove("selected");
                
            clicked_element.classList.add("selected");
        }
        
        updateAverageRating(msg);
    });
}

function handleAction(event) {
    event.preventDefault();
    var clickable = this;
    var action = clickable.name;
    var undo = clickable.classList.contains("selected");
    
    var url =   "releaseId" in clickable.dataset ? "/release/" + clickable.dataset.releaseId
              : "/track/" + clickable.dataset.trackId
    
    $.ajax({
        method: "POST",
        url: url,
        data: {"action": undo ? "un" + action : action}
        
    }).done(function (msg) {
        if (msg.error)
            return;
        
        var classes = clickable.classList;
        classes[undo ? "remove" : "add"]("selected");
    })
}

if (typeof Chart !== "undefined") {
    Chart.defaults.global.legend.display = false;
    Chart.defaults.global.animation = false;

    Chart.defaults.global.scaleLineColor = palette[1];
    Chart.defaults.global.scaleFontFamily = "Signika";
    Chart.defaults.global.scaleFontSize = 14;
}

function renderChart(canvas, labels, options) {
    if ("chart" in canvas)
        canvas.chart.destroy();
    
    canvas.chart = new Chart(canvas.getContext("2d"), options);
}

defaultBarOptions = {scales: {xAxes: [{categoryPercentage: 1, barPercentage: 0.85}]}};

function renderBarChart(canvas, labels, data, options=defaultBarOptions) {
    renderChart(canvas, labels, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                data: data,
                borderColor: palette[0],
                backgroundColor: "rgba(0,0,0, 0)",
                hoverBackgroundColor: palette[0],
                borderWidth: 1.5,
                
            }]
        },
        options: options
    });
}

function renderRatingCounts(canvas) {
    var ratings = ["1", "2", "3", "4", "5", "6", "7", "8"];
    renderBarChart(canvas, ratings, userDatasets.ratingCounts);
}

function renderYearCounts(canvas) {
    var [labels, data] = userDatasets.releaseYearCounts;
    
    /*Pad the front of the dataset to the start of a decade*/
    var extraYears = labels[0] % 10;
    data = Array(extraYears).fill(0).concat(data);
    labels = Array.from(Array(extraYears), (x, i) => labels[0] - extraYears + i).concat(labels);
    
    renderBarChart(canvas, labels, data, {
        scales: {
            xAxes: [{
                categoryPercentage: 1,
                barPercentage: 0.8,
                type: "time",
                time: {parser: "YYYY", unit: "year", unitStepSize: 10
            }}]
        }
    });
}

$(document).ready(function ($) {
    $("a#login").click(function (event) {
        event.preventDefault();
        $(".popup-content:not(#login-popup)").toggle(false);
        $("#login-popup").toggle({duration: 100});
        $("#login-popup [name='username']").focus()
    });
    
    $("a#register").click(function (event) {
        event.preventDefault();
        $(".popup-content:not(#register-popup)").toggle(false);
        $("#register-popup").toggle({duration: 100});
        $("#register-popup [name='username']").focus()
    });
    
    $("#logout").parent().remove();
    $("#user-more").show();
    
    $("#user-more").click(function (event) {
        event.preventDefault();
        $(".popup-content:not(#user-popup)").toggle(false);
        $("#user-popup").toggle({duration: 50});
    });
    
    $("form#search input[type='submit']").click(function (event) {
        /*Cancel the click if the search query is empty*/
        if ($("form#search [name='query']").val().trim() == "")
            event.preventDefault();
    });
    
    $(".action-list .clickable").click(handleAction);
    $(".action.clickable").click(handleAction);
    
    if (typeof Chart !== "undefined") {
        $("input[type=radio][name=chart-select]").change(function () {
            var canvas = document.getElementById("user-chart");
            
            switch (this.value) {
            case "rating-counts": renderRatingCounts(canvas); break;
            case "year-counts": renderYearCounts(canvas); break;
            }
        });
        
        /*Trigger a change on the default checked radio to create a chart*/
        $("input[type=radio][name=chart-select]:checked").change();
    }
    
    $(".editable.rating-description")
    .attr("contenteditable", "")
    .blur(function (event) {
        var description = event.target.innerHTML;
        var rating = event.target.dataset.rating;
        
        $.post("/rating-descriptions", {rating: rating, description: description}, function (msg) {
            if (msg.error)
                return; //todo
            
            event.target.innerHTML = msg.description;
        });
    });
    
    $(".load-more").click(function (event) {
        event.preventDefault();
        
        var dataset = event.target.dataset;
        
        $.get(dataset.endpoint, {last_action: dataset.last_action}, function (msg) {
            if (msg.error)
                    return; //todo
            
            dataset.last_action= msg.last_action;
            
            var target = $(event.target).closest(".load-more-area").find(".load-more-target");
            target.append(msg.html);
        });
    });
    
    //The jQuery autocomplete API relies on each result having a "label" field.
    //Even if _renderItem is overriden not to use it, it is still used when selecting
    //an item with the keyboard.
    function assignLabels(results, f) {
        results.map(function (result) {
            result.label = f(result);
        });
    }
    
    //From http://stackoverflow.com/questions/34704997/jquery-autocomplete-in-flask
    $("#autocomplete").autocomplete({
        minLength: 2,
        source: function (request, response) {
            $.getJSON("/search/" + request.term, {
                return_json: 1
            }, function (data) {
                assignLabels(data.results, result => result.name);
                response(data.results);
            });
        },
        select: function (event, ui) {
            window.location.href = ui.item.url;
        }
    });
    
    var mb_autocomplete = $("#autocomplete-mb").autocomplete({
        minLength: 2,
        source: function (request, response) {
            $.getJSON("/add-artist-search/" + request.term, {
                return_json: 1
            }, function (data) {
                assignLabels(data.results, result => result.name);
                response(data.results);
            });
        },
        select: function (event, ui) {
                $.ajax({
                    method: "POST",
                    url: "/add-artist",
                    data: {'artist-id': ui.item.id}
                });
                window.alert("The artist is being added")
        }
    }).data("ui-autocomplete");
    
    if (mb_autocomplete) {
        mb_autocomplete._renderItem = function (ul, item) {
            var li = $("<li>")
                .addClass("ui-menu-item")
                .appendTo(ul);
            
            var a = $("<a>")
                .append(item.name + " ")
                .appendTo(li);
                
            if ("disambiguation" in item || "area" in item)
                $("<span>")
                    .addClass("de-emph")
                    .append("disambiguation" in item ? item.disambiguation : item.area.name)
                    .appendTo(a);
                    
            return li;
        }
    }
});
