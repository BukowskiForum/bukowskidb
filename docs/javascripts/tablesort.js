document$.subscribe(function() {
    var tables = document.querySelectorAll("article table:not([class])")
    tables.forEach(function(table) {
        // Update header attributes for specific columns before initializing Tablesort
        var headers = table.querySelectorAll("thead th");
        headers.forEach(function(th) {
            var headerText = th.textContent.trim();
            
            // Columns to disable sorting on
            var disabledColumns = [
                "written date", "month"
            ];
            
            if (disabledColumns.includes(headerText.toLowerCase())) {
                th.setAttribute("data-sort-method", "none");
            }
            // Keep existing sort method assignments
            else if (headerText.toLowerCase().includes("date")) {
                th.setAttribute("data-sort-method", "date");
            }
            if (headerText.toLowerCase() === "collected" || 
                headerText.toLowerCase() === "major" ||
                headerText.toLowerCase() === "manuscript") {
                th.setAttribute("data-sort-method", "number");
            }
        });
        new Tablesort(table)
    })
})