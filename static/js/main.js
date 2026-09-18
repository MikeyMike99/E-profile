/* Marker: Start of Integrated main.js */

document.addEventListener('DOMContentLoaded', () => {
    console.log("Architect_OS v.2.6.0: Logic Core Online...");

    // 1. CYBER-BUTTON ENGINE
    const buttons = document.querySelectorAll('.cyber-button');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            btn.style.transform = "scale(0.95)";
            setTimeout(() => btn.style.transform = "scale(1)", 100);
        });
    });

    // 2. TAB TRACKING (Fixed for Dynamic Routes)
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.tab-item');

    navLinks.forEach(link => {
        // This ensures /projects matches even if we are deep in a sub-route
        if (currentPath.startsWith(link.getAttribute('href'))) {
            link.classList.add('active-node'); // Use a class for CSS glow
            link.setAttribute('aria-current', 'page');
        }
    });

    // 3. THE SURGERY PORTAL BRIDGE
    // This allows any "Surgery" button to talk to the /api/ nested blueprint
    window.openSurgery = function (projectName) {
        const target = (projectName === 'root' || projectName === 'SYSTEM_CORE') ? 'root' : projectName;

        // NEW PATH: Matches your app.py /api/projects prefix
        const url = `/api/projects/surgery/interface/${target}`;

        const portal = window.open(url, '_blank');
        if (portal) {
            console.log(`PORTAL_OPEN: ${target.toUpperCase()}`);
        } else {
            alert("POPUP_BLOCKED: PLEASE_ALLOW_SURGICAL_INTERFACE");
        }
    };

    // 4. ENGINE EXECUTION BRIDGE
    window.launchEngine = function (name) {
        // Targets the /api/projects/execute route
        fetch(`/api/projects/execute/${name}`)
            .then(res => res.text())
            .then(msg => console.log(`STDOUT: ${msg}`))
            .catch(err => console.error(`SIG_TERM: ${err}`));
    };
});

/* Marker: End of main.js */