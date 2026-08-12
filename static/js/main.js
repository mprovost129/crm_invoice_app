// Main JavaScript entry point.

function getCookie(name) {
    const cookie = document.cookie
        .split(";")
        .map((value) => value.trim())
        .find((value) => value.startsWith(`${name}=`));

    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : null;
}

document.body.addEventListener("htmx:configRequest", (event) => {
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
        event.detail.headers["X-CSRFToken"] = csrfToken;
    }
});
