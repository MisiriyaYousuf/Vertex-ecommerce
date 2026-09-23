// signup.js

(function () {

    const form = document.getElementById("signupForm");

    if (!form) return;

    const fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "city",
        "country",
        "address",
        "password1",
        "password2"
    ];

    fields.forEach(function (name) {

        const input = document.getElementById(`id_${name}`);
        const container = document.getElementById(`field-${name}`);
        const error = document.getElementById(`error-${name}`);

        if (!input || !container) return;

        
        input.addEventListener("focus", function () {
            container.classList.add("focused");
        });

        input.addEventListener("blur", function () {
            container.classList.remove("focused");

            if (input.value.trim() !== "") {
                container.classList.add("success");
            } else {
                container.classList.remove("success");
            }
        });

        
        input.addEventListener("input", function () {

            container.classList.remove("error");

            if (error) {
                error.style.display = "none";
            }

            if (input.value.trim() !== "") {
                container.classList.add("success");
            } else {
                container.classList.remove("success");
            }

        });

    });

    // submissions handling function
    form.addEventListener("submit", function () {

        const submitBtn = document.getElementById("submitBtn");

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML =
                '<i class="fas fa-spinner fa-spin"></i> Creating Account...';
        }

    });

})();

document.addEventListener("DOMContentLoaded", function () {

    const form = document.getElementById("signupForm");

    if (!form) {
        return;
    }

    window.addEventListener("pageshow", function (event) {

        const navigationEntries = performance.getEntriesByType("navigation");

        if (
            navigationEntries.length > 0 &&
            navigationEntries[0].type === "reload"
        ) {

            // Clear all form values
            form.reset();

            // Clear Django validation errors
            document.querySelectorAll(".error-text").forEach(function (element) {
                element.remove();
            });

            // Clear form feedback
            const feedback = document.getElementById("formFeedback");

            if (feedback) {
                feedback.innerHTML = "";
            }

            // Explicitly clear all inputs
            form.querySelectorAll("input").forEach(function (input) {
                input.value = "";
            });
        }

    });

});