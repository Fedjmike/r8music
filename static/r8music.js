function updateAverageRating(averageRating) {
    if (!averageRating) {
        $("#average-rating-section").css("display", "none");
        
    } else {
        $("#average-rating-section").css("display", "inline");
        $("#average-rating").text(averageRating.toFixed(1));
    }
}

function rateRelease(clicked_element, release_id, rating) {
    /*User clicked the already selected rating => unrate*/
    var is_undo = clicked_element.classList.contains("selected");
    var action = is_undo ? "unrate" : "rate";
    
    $.ajax({
        method: "POST",
        url: "/releases/" + release_id + "/" + action + "/",
        data: {rating: rating}
    }).done(function (msg) {
        if (msg.error)
            return;
            
        /*Success, update rating widget*/
        
        if (is_undo) {
            clicked_element.classList.remove("selected");
        
        } else {
            var siblings = clicked_element.parentNode.children;
            
            for (var i = 0; i < siblings.length; i++)
                siblings[i].classList.remove("selected");
                
            clicked_element.classList.add("selected");
        }
        
        updateAverageRating(msg.averageRating);
    });
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

function renderReleaseYearCounts(canvas) {
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

function renderListenMonthCounts(canvas) {
    var [labels, data] = userDatasets.listenMonthCounts;
    
    renderBarChart(canvas, labels, data, {
        scales: {
            xAxes: [{
                categoryPercentage: 1,
                barPercentage: 0.8,
                type: "time",
                time: {parser: "YYYY-MM", unit: "month", unitStepSize: 6
            }}]
        }
    });
}

function elementInScroll(elem) {
    var docViewTop = $(window).scrollTop();
    var docViewBottom = docViewTop + $(window).height();

    var elemTop = $(elem).offset().top;
    var elemBottom = elemTop + $(elem).height();

    return elemBottom <= docViewBottom && elemTop >= docViewTop;
};

var stahp = false;
var autoload = function() {
    if (!stahp && elementInScroll("#autoload-trigger")) {
        var autoloadTrigger = document.getElementById("autoload-trigger");
        stahp = true;
        
        $(autoloadTrigger).text("Loading");
        
        var next_page_no = parseInt(autoloadTrigger.dataset.page_no) + 1;
        
        $.get(autoloadTrigger.dataset.endpoint, {page_no: next_page_no}, function (msg) {
            if (msg.error)
                    return; //todo
            
            autoloadTrigger.dataset.page_no = next_page_no;
            
            $(autoloadTrigger).text("Load more");
            
            var target = $(autoloadTrigger).closest(".load-more-area").find(".load-more-target");
            target.append(msg);
            stahp = false;
        });
    };
};

$(document).ready(function ($) {
    if (document.getElementById("autoload-trigger")) {
        $(window).on('scroll',  _.debounce(autoload, 200));
    };
    
    $("#logout").parent().remove();
    $("#user-more").show();
    
    $("#user-more").click(function (event) {
        event.preventDefault();
        $(".popup-content:not(#user-popup)").toggle(false);
        $("#user-popup").toggle({duration: 50});
    });
    
    $("form#search input[type='submit']").click(function (event) {
        /*Cancel the click if the search query is empty*/
        if ($("form#search [name='q']").val().trim() == "")
            event.preventDefault();
    });
    
    if (typeof Chart !== "undefined") {
        renderRatingCounts(document.getElementById("rating-counts-chart"));
        renderReleaseYearCounts(document.getElementById("release-year-counts-chart"));
        renderListenMonthCounts(document.getElementById("listen-month-counts-chart"));
    }
    
    $(".editable.rating-description")
    .attr("contenteditable", "")
    .blur(function (event) {
        var description = event.target.innerHTML;
        var rating = event.target.dataset.rating;
        
        $.post("/settings/rating-description", {rating: rating, description: description}, function (msg) {
            if (msg.error)
                return; //todo
        });
    });
    
    $(".load-more").click(function (event) {
        event.preventDefault();
        
        var dataset = event.target.dataset;
        
        var next_page_no = parseInt(dataset.page_no) + 1;
        
        $.get(dataset.endpoint, {page_no: next_page_no}, function (msg) {
            if (msg.error)
                    return; //todo
            
            dataset.page_no = msg.next_page_no;
            
            var target = $(event.target).closest(".load-more-area").find(".load-more-target");
            target.append(msg);
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
            $.getJSON("/api/search", {
                q: request.term, 
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
