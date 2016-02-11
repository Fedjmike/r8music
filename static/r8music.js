function rateRelease(clicked_element, release_id, rating) {
    $.ajax({
        method: "POST",
        url: "/rate/" + release_id + "/" + rating
        
    }).done(function (msg) {
        if (msg != "ok")
            return;
        
        var siblings = clicked_element.parentNode.children;
        
        for (var i = 0; i < siblings.length; i++)
            siblings[i].classList.remove("selected");
            
        clicked_element.classList.add("selected");
    });
}