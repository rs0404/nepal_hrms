import { createResource } from "frappe-ui"

const companyCurrency = createResource({
	url: "hrms.api.get_company_currencies",
	auto: false,
})

const currencySymbols = createResource({
	url: "hrms.api.get_currency_symbols",
	auto: false,
})

export function getCompanyCurrency(company) {
	if (!companyCurrency.data && !companyCurrency.loading) companyCurrency.fetch()
	return companyCurrency?.data?.[company]?.[0]
}

export function getCompanyCurrencySymbol(company) {
	if (!companyCurrency.data && !companyCurrency.loading) companyCurrency.fetch()
	return companyCurrency?.data?.[company]?.[1]
}

export function getCurrencySymbol(currency) {
	if (!currencySymbols.data && !currencySymbols.loading) currencySymbols.fetch()
	return currencySymbols?.data?.[currency]
}
