document.addEventListener("DOMContentLoaded", () => {
  const navLinks = [...document.querySelectorAll(".topnav a")];
  const sections = navLinks
    .map((link) => {
      const target = link.getAttribute("href");
      return target && target.startsWith("#") ? document.querySelector(target) : null;
    })
    .filter(Boolean);

  if ("IntersectionObserver" in window && sections.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        const id = `#${visible.target.id}`;
        navLinks.forEach((link) => {
          link.classList.toggle("is-active", link.getAttribute("href") === id);
        });
      },
      {
        rootMargin: "-30% 0px -55% 0px",
        threshold: [0.2, 0.45, 0.7],
      },
    );

    sections.forEach((section) => observer.observe(section));
  }
});
