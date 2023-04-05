import json

def fix_key_order(searchresults_list):
    # Fix key order of searchresults_list. Because due to the parallel processing, the order of the string-index searchresults_list[i][str(i)] is not guaranteed.
    # Iterate through the list with searchresults_list[i] and put the value of i into each searchresult (searchresults_list[i][str(i)])
    # searchresult has always only one entry (internal convention, for now)
    fixed_searchresults_list = []
    for i in range(len(searchresults_list)):
        searchresult = searchresults_list[i]
        new_searchresult = {str(i): searchresult[next(iter(searchresult))]} # Get the first entry of searchresult and change the key to i
        fixed_searchresults_list.append(new_searchresult)
    return fixed_searchresults_list



searchresults = [{'0': {'URL': 'https://commission.europa.eu/strategy-and-policy/priorities-2019-2024/promoting-our-european-way-life/statistics-migration-europe_de', 'summary': 'Die Seite enthält keine Informationen darüber, welches europäische Land noch gründlich COVID-Infektionen erfasst.', 'prozent': 'unknown', 'keyword': 'Europäische Länder COVID-19 Statistik'}}, {'1': {'URL': 'https://www.ecdc.europa.eu/en/covid-19/country-overviews', 'summary': 'Die Webseite https://www.ecdc.europa.eu/en/covid-19/country-overviews bietet eine Übersicht über die COVID-19-Situation in europäischen Ländern. Es werden Daten zu nationalen 14-Tage-Melderate (Fälle und Todesfälle), Krankenhaus- und Intensivstationseinweisungen, Testungen und Altersgruppen-Melderate bereitgestellt.', 'prozent': '60.0', 'keyword': 'Europäische Länder COVID-19 Statistik'}}, {'1': {'URL': 'https://npgeo-corona-npgeo-de.hub.arcgis.com/', 'summary': 'Die Webseite https://npgeo-corona-npgeo-de.hub.arcgis.com/ bietet eine umfassende Übersicht über die COVID-19-Fallzahlen in Europa. Die Daten werden von verschiedenen nationalen Gesundheitsbehörden gesammelt und regelmäßig aktualisiert. Die Webseite bietet eine interaktive Karte, auf der die aktuellen Fallzahlen für jedes europäische Land angezeigt werden.', 'prozent': '60.0', 'keyword': 'Coronavirus Fallzahlen Erhebung Europa'}}, {'2': {'URL': 'https://www.corona-in-zahlen.de/europa/', 'summary': 'Die Webseite "corona-in-zahlen.de" bietet aktuelle COVID-19 Kennzahlen für alle Länder in Europa. Es werden sowohl absolute als auch relative Kennzahlen berechnet, um eine bessere Vergleichbarkeit zu ermöglichen. Die höchsten Neuinfektionsraten pro 100.000 Einwohner in der letzten Woche wurden in Österreich, Zypern, San Marino, Slowenien und Guernsey (Kanalinsel) gemeldet. Die Länder mit den höchsten gemeldeten Infektionen sind Frankreich, Deutschland, Italien, das Vereinigte Königreich und Russland. Es gibt auch Informationen zu den Ländern mit den meisten Todesfällen und den höchsten Letalitätsraten.', 'prozent': '30.0', 'keyword': 'Europäische Länder COVID-19 Statistik'}}]
print(json.dumps(fix_key_order(list(searchresults)), indent=4))