(function () {
  var charts = document.getElementById("charts");
  var fallback = document.getElementById("fallback");

  // Chart.js comes from a CDN. If it didn't load, show the tables instead.
  if (typeof Chart === "undefined") {
    charts.classList.add("d-none");
    fallback.classList.remove("d-none");
    return;
  }

  var d = window.DASH;
  var colors = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2", "#edc948", "#b07aa1", "#9c755f"];
  var base = { maintainAspectRatio: false };

  function draw(id, type, labels, values, label, options) {
    new Chart(document.getElementById(id), {
      type: type,
      data: {
        labels: labels,
        datasets: [{
          label: label,
          data: values,
          backgroundColor: type === "pie" ? colors : colors[0],
          borderColor: colors[0]
        }]
      },
      options: Object.assign({}, base, options || {})
    });
  }

  var noLegend = { plugins: { legend: { display: false } } };

  draw("daily", "line", d.daily.labels, d.daily.values, "Revenue", noLegend);
  draw("categories", "pie", d.categories.labels, d.categories.values, "Revenue");
  draw("top", "bar", d.top_items.labels, d.top_items.values, "Sold",
       Object.assign({ indexAxis: "y" }, noLegend));
  draw("hours", "bar", d.hours.labels, d.hours.values, "Orders", noLegend);
  draw("staff", "bar", d.staff.labels, d.staff.revenue, "Revenue", noLegend);
})();
