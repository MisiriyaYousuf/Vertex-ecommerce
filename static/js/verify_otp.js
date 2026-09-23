document.addEventListener("DOMContentLoaded", function () {

    const otpInput = document.querySelector("#id_otp");
    const countdown = document.getElementById("countdown");
    const otpTimer = document.getElementById("otp-timer");
    const submitBtn = document.getElementById("verify-button");
    const resendSection = document.getElementById("resend-section");

    let timer = null;

    if (!otpTimer) {
        return;
    }

    const otpExpiresAt = otpTimer.dataset.expiresAt;
    if (otpInput) {

        otpInput.focus();

        otpInput.addEventListener("input", function () {

            this.value = this.value.replace(/\D/g, "");

            if (this.value.length > 6) {
                this.value = this.value.slice(0, 6);
            }

        });
    }

    function updateTimer() {

        if (!otpExpiresAt) {

            countdown.textContent = "00:00";

            otpTimer.textContent = "OTP has expired.";
            otpTimer.style.color = "#dc3545";

            if (otpInput) {
                otpInput.disabled = true;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
            }

            if (resendSection) {
                resendSection.style.display = "block";
            }

            if (timer) {
                clearInterval(timer);
            }

            return;
        }


        const now = new Date().getTime();

        const expiry = new Date(
            otpExpiresAt
        ).getTime();

        const remaining = expiry - now;

        if (remaining <= 0) {

            countdown.textContent = "00:00";

            otpTimer.innerHTML = "OTP has expired.";

            otpTimer.style.color = "#dc3545";


            if (otpInput) {
                otpInput.disabled = true;
            }


            if (submitBtn) {
                submitBtn.disabled = true;
            }

            if (resendSection) {
                resendSection.style.display = "block";
            }


            if (timer) {
                clearInterval(timer);
            }

            return;
        }

        const totalSeconds =
            Math.floor(remaining / 1000);

        const minutes =
            Math.floor(totalSeconds / 60);

        const seconds =
            totalSeconds % 60;

        countdown.textContent =
            String(minutes).padStart(2, "0") +
            ":" +
            String(seconds).padStart(2, "0");

    }

    updateTimer();

    timer = setInterval(
        updateTimer,
        1000
    );

    const alerts =
        document.querySelectorAll(".alert");


    alerts.forEach(function (alert) {

        setTimeout(function () {

            alert.style.opacity = "0";

            setTimeout(function () {

                alert.remove();

            }, 500);

        }, 3000);

    });

});