function replaceNepalHrmsWorkspaceIcon() {
	const customIconPath = "/assets/nepal_hrms/icon/nepal-hrms.svg";
	const targetHref = `#icon-${customIconPath}`;

	document.querySelectorAll("svg.icon use").forEach((useTag) => {
		const href = useTag.getAttribute("href");
		if (href !== targetHref) return;

		const svg = useTag.closest("svg");
		const container = svg?.closest(".sidebar-item-icon");
		if (!container || container.querySelector("img, .nh-workspace-icon")) return;

		container.innerHTML = `<svg class="nh-workspace-icon" width="20" height="20" viewBox="0 0 20 20" fill="#DC143C" xmlns="http://www.w3.org/2000/svg">
			<path d="M4.4 4.7L11.05 8.35H4.4V4.7Z" fill="#DC143C"/>
			<path d="M4.4 8.15L13.15 13.7H4.4V8.15Z" fill="#DC143C"/>
			<circle cx="14.85" cy="7.05" r="1.4" fill="#DC143C"/>
			<path d="M12.25 13.75C12.25 11.7 13.3 10.45 14.85 10.45C16.4 10.45 17.45 11.7 17.45 13.75H12.25Z" fill="#DC143C"/>
			<path d="M16.8551 0H3.14489C1.41062 0 0 1.41062 0 3.14489V16.8551C0 18.5894 1.41062 20 3.14489 20H16.8551C18.5894 20 20 18.5894 20 16.8551V3.14489C20 1.41062 18.589 0 16.8551 0ZM19.168 16.8551C19.168 18.1305 18.1305 19.168 16.8551 19.168H3.14489C1.86946 19.168 0.831981 18.1305 0.831981 16.8551V3.14489C0.831981 1.86946 1.86946 0.831981 3.14489 0.831981H16.8551C18.1305 0.831981 19.168 1.86946 19.168 3.14489V16.8551Z" fill="#DC143C"/>
		</svg>`;
	});
}

frappe.after_ajax(() => {
	setTimeout(replaceNepalHrmsWorkspaceIcon, 1000);
});

frappe.router.on("change", () => {
	setTimeout(replaceNepalHrmsWorkspaceIcon, 1000);
});
