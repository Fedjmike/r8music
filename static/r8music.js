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
    unrating = clicked_element.classList.contains("selected");
    
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
    clickable = this;
    action = clickable.name;
    undo = clickable.classList.contains("selected");
    
    $.ajax({
        method: "POST",
        url: "/release/" + clickable.dataset.releaseId,
        data: {"action": undo ? "un" + action : action}
        
    }).done(function (msg) {
        if (msg.error)
            return;
        
        classes = clickable.classList;
        classes[undo ? "remove" : "add"]("selected");
    })
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
});
