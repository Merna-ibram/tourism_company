(function () {
    "use strict";

    // الـ Html field مبيشغلش <script> جوّاه، فبنستخدم listener واحد على الصفحة كلها.

    function closeAll(dash) {
        dash.querySelectorAll(".o_trip_detail").forEach(function (p) {
            p.style.display = "none";
        });
        dash.querySelectorAll(".o_trip_card").forEach(function (c) {
            c.style.boxShadow = "";
        });
    }

    document.addEventListener("click", function (ev) {
        var dash = document.querySelector(".o_trip_dash");
        if (!dash) {
            return;
        }
        var target = ev.target;

        // الضغط جوّه القايمة نفسها (سكرول/اختيار نص) مايقفلهاش
        if (target.closest(".o_trip_detail")) {
            return;
        }

        var card = target.closest(".o_trip_card[data-detail]");
        if (!card || !dash.contains(card)) {
            closeAll(dash); // ضغطة بره = يقفل كله
            return;
        }

        var panel = dash.querySelector(
            '.o_trip_detail[data-detail-for="' + card.dataset.detail + '"]'
        );
        var wasOpen = panel && panel.style.display !== "none";
        closeAll(dash); // يقفل اللي مفتوح قبل ما يفتح الجديد
        if (panel && !wasOpen) {
            panel.style.display = "block";
            card.style.boxShadow = "0 0 0 2px " + (card.dataset.color || "#714B67");
        }
    });
})();