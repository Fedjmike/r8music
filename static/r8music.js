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

function handleReleaseAction(event) {
    event.preventDefault();
    var clickable = this;
    var action = clickable.name;
    var undo = clickable.classList.contains("selected");
    
    $.ajax({
        method: "POST",
        url: "/release/" + clickable.dataset.releaseId,
        data: {"action": undo ? "un" + action : action}
        
    }).done(function (msg) {
        if (msg.error)
            return;
        
        var classes = clickable.classList;
        classes[undo ? "remove" : "add"]("selected");
    })
}

if (typeof Chart !== "undefined") {
    Chart.defaults.global.animation = false;

    Chart.defaults.global.scaleLineColor = palette[1];
    Chart.defaults.global.scaleFontFamily = "Signika";
    Chart.defaults.global.scaleFontSize = 14;

    Chart.defaults.Bar.barStrokeWidth = 1.5;
    Chart.defaults.Bar.barValueSpacing = 1;
}

function renderRatingCounts(canvas) {
    if ("chart" in canvas)
        canvas.chart.destroy();
    
    canvas.chart = new Chart(canvas.getContext("2d")).Bar({
        labels: ["1", "2", "3", "4", "5", "6", "7", "8"],
        datasets: [{
            data: userDatasets.ratingCounts,
            strokeColor: palette[0],
            fillColor: "rgba(0,0,0, 0)",
            highlightFill: palette[0]
        }]
    });
}

function renderYearCounts(canvas) {
    if ("chart" in canvas)
        canvas.chart.destroy();
    
    var [labels, data] = userDatasets.releaseYearCounts;
    
    //todo: this is shit
    labels = labels.map(year => year % 10 == 0 ? year : "");
    
    canvas.chart = new Chart(canvas.getContext("2d")).Bar({
        labels: labels,
        datasets: [{
            data: data,
            strokeColor: palette[0],
            fillColor: "rgba(0,0,0, 0)",
            highlightFill: palette[0]
        }]
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
        if ($("form#search [name='query']").val() == "")
            event.preventDefault();
    });
    
    $(".action .clickable").click(handleReleaseAction);
    
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
});
