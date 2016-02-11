function unrateRelease(clicked_element, release_id) {
    $.ajax({
        method: "POST",
        url: "/unrate/" + release_id
        
    }).done(function (msg) {
        if (msg != "ok")
            return;
            
        clicked_element.classList.remove("selected");
    })
}

function rateRelease(clicked_element, release_id, rating) {
    /*User clicked the already selected rating
       => unrate*/
    if (clicked_element.classList.contains("selected")) {
        unrateRelease(clicked_element, release_id);
        return;
    }
    
    $.ajax({
        method: "POST",
        url: "/rate/" + release_id + "/" + rating
        
    }).done(function (msg) {
        if (msg != "ok")
            return;
            
        /*Success, update rating widget*/
        
        var siblings = clicked_element.parentNode.children;
        
        for (var i = 0; i < siblings.length; i++)
            siblings[i].classList.remove("selected");
            
        clicked_element.classList.add("selected");
    });
}