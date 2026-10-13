// Pull-to-refresh for every page built on BaseLayout.
//
// The data modules hold app-wide resources that live for the whole session;
// a page remount alone would not refetch them. Reload the ones already in use
// -- fetched once, or holding data -- and leave the rest to load as they would.
const dataModules = import.meta.glob("../data/*.js")

function isResource(value) {
	return value && typeof value === "object" && typeof value.reload === "function"
}

export async function reloadLoadedResources() {
	const modules = await Promise.all(Object.values(dataModules).map((load) => load()))
	const reloads = []
	for (const module of modules) {
		for (const value of Object.values(module)) {
			if (isResource(value) && (value.fetched || value.data != null)) {
				reloads.push(Promise.resolve(value.reload()).catch(() => {}))
			}
		}
	}
	await Promise.all(reloads)
}
