// Ratings

function updateAverageRating(averageRating) {
  if (!averageRating) {
    $("#average-rating-section").css("display", "none");
    
  } else {
    $("#average-rating-section").css("display", "inline");
    $("#average-rating").text(averageRating.toFixed(1));
  }
}

function rateRelease(clicked_element, release_id, rating) {
  // User clicked the already selected rating => unrate
  const is_undo = clicked_element.classList.contains("selected");
  const action = is_undo ? "unrate" : "rate";
  
  $.ajax({
    method: "POST",
    url: "/releases/" + release_id + "/" + action + "/",
    data: {rating: rating}
  }).done(function (msg) {
    if (msg.error) {
      return;
    }
    
    // Success, update rating widget
    
    if (is_undo) {
      clicked_element.classList.remove("selected");
    
    } else {
      for (const sibling of clicked_element.parentNode.children) {
        sibling.classList.remove("selected");
      }
      
      clicked_element.classList.add("selected");
    }
    
    updateAverageRating(msg.averageRating);
  });
}

// Charts

if (typeof Chart !== "undefined") {
  Chart.defaults.global.legend.display = false;
  Chart.defaults.global.animation = false;

  Chart.defaults.global.scaleLineColor = palette[1];
  Chart.defaults.global.scaleFontFamily = "Signika";
  Chart.defaults.global.scaleFontSize = 14;
}

function renderChart(canvas, labels, options) {
  if ("chart" in canvas) {
    canvas.chart.destroy();
  }
  
  canvas.chart = new Chart(canvas.getContext("2d"), options);
}

function renderBarChart(canvas, labels, data, options={}, datasetOptions={}) {
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
        categoryPercentage: 1,
        barPercentage: 0.8,
        ...datasetOptions
      }]
    },
    options: options
  });
}

function timeBarChartOptions(timeOptions) {
  return {
    scales: {
      xAxes: [{
        type: "time",
        time: timeOptions,
        // Add spacing either side of the x axis
        offset: true,
        // Show bars between the grid lines 
        gridLines: {offsetGridLines: true},
      }]
    }
  };
}

function renderRatingCounts(canvas) {
  const ratings = ["1", "2", "3", "4", "5", "6", "7", "8"];
  renderBarChart(canvas, ratings, userDatasets.ratingCounts,
    datasetOptions={categoryPercentage: 1, barPercentage: 0.85}
  );
}

function renderReleaseYearCounts(canvas) {
  let [labels, data] = userDatasets.releaseYearCounts;

  const stepSize = 5;
  
  // Pad the front of the dataset to an even step size
  const extraYears = labels[0] % stepSize;
  data = Array(extraYears).fill(0).concat(data);
  labels = Array.from(Array(extraYears), (x, i) => labels[0] - extraYears + i).concat(labels);
  
  labels = labels.map(year => year.toString());
  
  const chartOptions = timeBarChartOptions({
    parser: "YYYY", unit: "year", unitStepSize: stepSize
  });
  renderBarChart(canvas, labels, data, chartOptions);
}

function renderListenMonthCounts(canvas) {
  const [labels, data] = userDatasets.listenMonthCounts;
  const chartOptions = timeBarChartOptions({
    parser: "YYYY-MM", unit: "month", unitStepSize: 6
  });
  renderBarChart(canvas, labels, data, chartOptions);
}

function setupCharts() {
  if (typeof Chart !== "undefined") {
    renderRatingCounts(document.getElementById("rating-counts-chart"));
    renderReleaseYearCounts(document.getElementById("release-year-counts-chart"));
    renderListenMonthCounts(document.getElementById("listen-month-counts-chart"));
  }
}

// 'Load more' button

function setupLoadMore() {
  $(".load-more").click(function (event) {
    event.preventDefault();
    
    const dataset = event.target.dataset;
    
    const next_page_no = parseInt(dataset.page_no) + 1;
    
    $.get(dataset.endpoint, {page_no: next_page_no}, function (msg) {
      if (msg.error) {
          return; //todo
      }

      dataset.page_no = next_page_no;
      
      const target = $(event.target).closest(".load-more-area").find(".load-more-target");
      target.append(msg);
    });
  });
}

// Scroll autoloading

function elementInScroll(elem) {
  const docViewTop = $(window).scrollTop();
  const docViewBottom = docViewTop + $(window).height();

  const elemTop = $(elem).offset().top;
  const elemBottom = elemTop + $(elem).height();

  return elemBottom <= docViewBottom && elemTop >= docViewTop;
};

let stopAutoloading = false;

function autoload() {
  if (!stopAutoloading && elementInScroll("#autoload-trigger")) {
    const autoloadTrigger = document.getElementById("autoload-trigger");
    stopAutoloading = true;
    
    $(autoloadTrigger).text("Loading");
    
    const next_page_no = parseInt(autoloadTrigger.dataset.page_no) + 1;
    
    $.get(autoloadTrigger.dataset.endpoint, {page_no: next_page_no}, function (msg) {
      if (msg.error) {
          return; //todo
      }
      
      autoloadTrigger.dataset.page_no = next_page_no;
      
      $(autoloadTrigger).text("Load more");
      
      const target = $(autoloadTrigger).closest(".load-more-area").find(".load-more-target");
      target.append(msg);
      stopAutoloading = false;
    });
  };
};

function setupAutoloading() {
  if (document.getElementById("autoload-trigger")) {
    $(window).on('scroll',  _.debounce(autoload, 200));
  };
}

// Navbar

function setupNavbar() {
  $("#logout").parent().remove();
  $("#user-more").show();
  
  $("#user-more").click(function (event) {
    event.preventDefault();
    $(".popup-content:not(#user-popup)").toggle(false);
    $("#user-popup").toggle({duration: 50});
  });
  
  $("form#search input[type='submit']").click(function (event) {
    // Cancel the click if the search query is empty
    if ($("form#search [name='q']").val().trim() == "") {
      event.preventDefault();
    }
  });
}

// Editable rating descriptions

function setupEditableRatingDescriptions() {
  $(".editable.rating-description")
    .attr("contenteditable", "")
    .blur(function (event) {
      const description = event.target.innerHTML;
      const rating = event.target.dataset.rating;
      
      $.post("/settings/rating-description", {rating: rating, description: description}, function (msg) {
        if (msg.error) {
          return; //todo
        }
      });
    });
}

// Search autocompletion

function assignAutocompletionLabels(results, f) {
  // The jQuery autocomplete API relies on each result having a "label" field.
  // Even if _renderItem is overriden not to use it, it is still used when selecting
  // an item with the keyboard.
  for (const result of results) {
    result.label = f(result);
  }
}

function setupSearchAutocompletion() {
  // From http://stackoverflow.com/questions/34704997/jquery-autocomplete-in-flask
  $("#autocomplete").autocomplete({
    minLength: 2,
    source: function (request, response) {
      $.getJSON("/api/search", {
        q: request.term, 
      }, function (data) {
        assignAutocompletionLabels(data.results, result => result.name);
        response(data.results);
      });
    },
    select: function (event, ui) {
      window.location.href = ui.item.url;
    }
  });
}

function setupMBSearchAutocompletion() {
  const mb_autocomplete = $("#autocomplete-mb").autocomplete({
    minLength: 2,
    source: function (request, response) {
      $.getJSON("/add-artist-search/" + request.term, {
        return_json: 1
      }, function (data) {
        assignAutocompletionLabels(data.results, result => result.name);
        response(data.results);
      });
    },
    select: function (event, ui) {
      $.ajax({
        method: "POST",
        url: "/add-artist",
        data: {'artist-id': ui.item.id}
      });
      window.alert("The artist is being added");
    }
  }).data("ui-autocomplete");
  
  if (mb_autocomplete) {
    mb_autocomplete._renderItem = function (ul, item) {
      const li = $("<li>")
        .addClass("ui-menu-item")
        .appendTo(ul);
      
      const a = $("<a>")
        .append(item.name + " ")
        .appendTo(li);
      
      if ("disambiguation" in item || "area" in item) {
        $("<span>")
          .addClass("de-emph")
          .append("disambiguation" in item ? item.disambiguation : item.area.name)
          .appendTo(a);
      }
      
      return li;
    }
  }
}

//

$(document).ready(function ($) {
  setupCharts();
  setupAutoloading();
  setupLoadMore();
  setupNavbar();
  setupEditableRatingDescriptions();
  setupSearchAutocompletion();
  setupMBSearchAutocompletion();
});
