# -*- coding: utf-8 -*-
import json
import re
import os
from dateutil import parser
import dateparser
import random
import numpy as np

page_number_pattern = r"(\b[1-9]\d{0,2}\b)(?:(?:\s+\S+){0,2}\s*)?$"
SEARCH_FOR_PAGE_NUMBER_RANGE = 40
#heading_pattern = r'(?:(?<=\n)|^)(?:(?=[^a-z\n])[^\n]+|(?:[ivxlc]+\.|[a-z][.)])\s*[^\n]+)(?<![\.,!\[\]\{\}\(\)“„"\'‚‘:»««»\/\\›‹‹›‐–\-’·…;,•\u2070-\u209F\u00B2\u00B3\u00B9\u00BC-\u00BE\u02C0-\u02FF])\s*(?=\n)' # to split long text by headlines
#heading_pattern = r'^[A-Za-z0-9]+\d*$'  # This regex will identify headlines (lines with only A-Z, a-z and 0-9, and no punctuation at the end of the line)
heading_pattern = r'^(?:(?=[^a-z])[^\n]+|(?:[ivxlc]+\.|[a-z][.)])\s*[^\n]+)(?<![\.,!\[\]\{\}\(\)“„"\'‚‘:»««»\/\\›‹‹›‐–\-’·…;,•\u2070-\u209F\u00B2\u00B3\u00B9\u00BC-\u00BE\u02C0-\u02FF])$' # to detect headlines in a single line of text

import re
MAX_VECTOR_LENGTH = 3000
CHAR_PER_SECTION = 20
NOHEADLINE = "Continuing previous section"
TEXT_WITHOUT_ANY_HEADLINES = "NO_HEADLINES_FOUND"


def extract_page_number(text, pattern):
    first_40 = text[:SEARCH_FOR_PAGE_NUMBER_RANGE]
    last_40 = text[-SEARCH_FOR_PAGE_NUMBER_RANGE:]

    match_first = re.search(pattern, first_40, flags=re.I)
    match_last = re.search(pattern, last_40, flags=re.I)

    page_number = None
    if match_first:
        page_number = match_first.group(1)
    elif match_last:
        page_number = match_last.group(1)

    return page_number

def create_json_object(data):
    json_object = []

    for i, (headline, text) in data.items():
        page_number = extract_page_number(text, page_number_pattern)

        entry = {
            "id": i,
            "headline": headline,
            "text_preview": text[:CHAR_PER_SECTION],
            "length": len(text),
            "page_number": page_number
        }
        json_object.append(entry)

    return json_object

def run_single_test(test_input, expected_output, weights):

    result, adjustments = detect_page_number(test_input, weights)
    if result != expected_output:
        for i, adjustment in enumerate(adjustments):
            weights[i] += adjustment * random.uniform(-0.1, 0.1)
        return 1, weights
    return 0, weights

def run_all_tests(test_cases, weights):
    failures = 0
    for test_input, expected_output in test_cases:
        f, weights = run_single_test(test_input, expected_output, weights)
        failures += f
    return failures, weights

def compute_gradient(failures, current_weights, test_cases):
    delta = 1e-3
    gradient = np.zeros(len(current_weights))

    for i in range(len(current_weights)):
        weights_plus = current_weights.copy()
        weights_plus[i] += delta
        failures_plus, _ = run_all_tests(test_cases, weights_plus)

        gradient[i] = (failures_plus - failures) / delta

    return gradient

def adam(test_cases, initial_weights, learning_rate=0.01, beta1=0.9, beta2=0.999, epsilon=1e-8, max_iterations=8000, tolerance=1e-4):
    weights = np.array(initial_weights)
    iteration = 0

    m = np.zeros(len(weights))
    v = np.zeros(len(weights))

    while iteration < max_iterations:
        iteration += 1
        failures, _ = run_all_tests(test_cases, weights)
        gradient = compute_gradient(failures, weights, test_cases)

        m = beta1 * m + (1 - beta1) * gradient
        v = beta2 * v + (1 - beta2) * gradient**2

        m_hat = m / (1 - beta1**iteration)
        v_hat = v / (1 - beta2**iteration)

        weights -= learning_rate * m_hat / (np.sqrt(v_hat) + epsilon)

        if iteration % 10 == 0:
            print(f"Iteration {iteration}: Failures = {failures}")

        if np.linalg.norm(gradient) < tolerance:
            break

    return weights.tolist()

def sgd(test_cases, initial_weights, learning_rate=0.1, max_iterations=8000, tolerance=1e-4):
    weights = np.array(initial_weights)
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        failures, _ = run_all_tests(test_cases, weights)
        gradient = compute_gradient(failures, weights, test_cases)
        weights -= learning_rate * gradient

        if iteration % 10 == 0:
            print(f"Iteration {iteration}: Failures = {failures}")

        if np.linalg.norm(gradient) < tolerance:
            break

    return weights.tolist()

def check_weights(optimized_weights, test_cases):
    count = 0
    for test_input, expected_output in test_cases:
        result, _ = detect_page_number(test_input, optimized_weights)
        if result != expected_output:
            count += 1
    return count

def adapt_weights_gradient():
    # Define your test cases here
    test_cases = [
    # Positive tests (expect True)
    ("Seite 1", True),
    ("Seite 1/10", True),
    ("Seite 1 of 10", True),
    ("Seite 1 von 10", True),
    ("Seite 1", True),
    ("  S. 10  ", True),
    ("  page 5", True),
    ("p.3", True),
    ("pg 123", True),
    ("1/10", True),
    ("1 of 10", True),
    ("   123 ", True),
    ("P 1", True),
    ("página 7", True),
    ("страница 42", True),
    ("σελ. 15", True),
    ("עמוד 22", True),
    ("ページ 36", True),
    ("stránka 11", True),
    ("sivu 9", True),
    ("oldal 17", True),
    ("Página 14", True),
    ("Folio 8", True),
    ("bladzijde 24", True),
    ("F. 32", True),
    ("b. 6", True),
    ("sayfa 20", True),
    ("صفحة 18", True),
    ("頁 31", True),
    ("页 21", True),
    ("str. 13", True),
    ("sida 10", True),
    ("Стр. 27", True),
    ("페이지 28", True),
    ("s. 12", True),
    ("Seite 1", True),
    ("234/699", True),
    ("699", True),
    ("I", True),
    ("V", True),
    ("X", True),
    ("iv", True),
    ("ix", True),
    ("XI", True),

    # Negative tests (expect False),
    ("Introduction", False),
    ("Chapter 1: The Beginning", False),
    ("Section 1.1 - Overview", False),
    ("1.1.4 The fourth subtopic", False),
    ("10-12-2023", False),
    ("12.03.2021", False),
    ("Seite 123a", False),
    ("Seite1", False),
    ("pages 1-10", False),
    ("1.2.3 Section title", False),
    ("§3.4.5 Legal reference", False),
    ("1.1 Figures and Tables", False),
    ("Part 2: The Journey", False),
    ("Section 12.5", False),
    ("Chapter 1.1", False),
    ("Lesson 5: The Basics", False),
    ("1a. Introduction", False),
    ("12% of the population", False),
    ("100m race", False),
    ("5-star hotel", False),
    ("3D printing", False),
    ("Version 2.1.0", False),
    ("Phone: +1 (555), 123-4567", False),
    ("PageRank Algorithm", False),
    ("1st place winner", False),
    ("3-point shot", False),
    ("Stage 4 cancer", False),
    ("50 shades of grey", False),
    ("12 Angry Men", False),
    ("5-star rating", False),
    ("A4 paper size", False),
    ("IPv4 address", False),
    ("10 Downing Street", False),
    ("Step 1: Prepare materials", False),
    ("Rule 5: Be consistent", False),
    ("Area 51", False),
    ("8-bit processor", False),
    ("2D barcode", False),
    ("4096-bit encryption", False),
    ("21st Century Skills", False),
    ("Title: Example Title", False),
    ("ISBN: 978-3-16-148410-0", False),
    ("DOI: 10.1000/xyz123", False),
    ("Formula: a^2 + b^2 = c^2", False),
    ("Date: 01/01/2023", False),
    ("2023-04-03", False),
    ("Note: This is important", False)
    ]
    
    length_test_weight = 0.7
    onlynumbers_test_weight = 0.5
    out_of_x_test_weight = 0.3
    out_of_x_test_weight2 = 0.55
    page_indicator_test_weight = 0.65
    date_test_weight = -0.19
    initial_weights  = [
    length_test_weight,
    onlynumbers_test_weight,
    out_of_x_test_weight,
    out_of_x_test_weight2,
    page_indicator_test_weight,
    date_test_weight
    ]
    final_number = 1
    old_final_number = len(test_cases)
    counter = 0
    while final_number > 0:
        #optimized_weights = sgd(test_cases, initial_weights)
        optimized_weights = adam(test_cases, initial_weights)
        print("Final weights:", optimized_weights)
        final_number = check_weights(optimized_weights, test_cases)
        print(f"final number of failed test cases: {final_number}")
        if final_number < old_final_number:
            initial_weights = [weight + random.uniform(-0.01, 0.01) for weight in optimized_weights]
            old_final_number = final_number
            counter = 0
        else:
            counter += 1
            if counter > 30:
                print("resetting, with slight variation")
                initial_weights  = [
                length_test_weight,
                onlynumbers_test_weight,
                out_of_x_test_weight,
                out_of_x_test_weight2,
                page_indicator_test_weight,
                date_test_weight
                ]
                initial_weights = [weight + random.uniform(-0.001, 0.001) for weight in initial_weights]
                counter = 0
    
    writemode = 'a'
    if not os.path.exists('resgradient'):
        os.makedirs('resgradient')
    # set the file path
    file_path = f'resgradient/log.txt'
    # open file in write mode
    with open(file_path, writemode, encoding="utf-8") as f:
        # write text to file
        f.writelines(["Final weights:", optimized_weights])
    print("done!")

def adapt_weights():
    # Define your test cases here
    test_cases = [
    # Positive tests (expect True)
    ("Seite 1", True),
    ("Seite 1/10", True),
    ("Seite 1 of 10", True),
    ("Seite 1 von 10", True),
    ("Seite 1", True),
    ("  S. 10  ", True),
    ("  page 5", True),
    ("p.3", True),
    ("pg 123", True),
    ("1/10", True),
    ("1 of 10", True),
    ("   123 ", True),
    ("P 1", True),
    ("página 7", True),
    ("страница 42", True),
    ("σελ. 15", True),
    ("עמוד 22", True),
    ("ページ 36", True),
    ("stránka 11", True),
    ("sivu 9", True),
    ("oldal 17", True),
    ("Página 14", True),
    ("Folio 8", True),
    ("bladzijde 24", True),
    ("F. 32", True),
    ("b. 6", True),
    ("sayfa 20", True),
    ("صفحة 18", True),
    ("頁 31", True),
    ("页 21", True),
    ("str. 13", True),
    ("sida 10", True),
    ("Стр. 27", True),
    ("페이지 28", True),
    ("s. 12", True),
    ("Seite 1", True),
    ("234/699", True),
    ("699", True),
    ("I", True),
    ("V", True),
    ("X", True),
    ("iv", True),
    ("ix", True),
    ("XI", True),

    # Negative tests (expect False),
    ("Introduction", False),
    ("Chapter 1: The Beginning", False),
    ("Section 1.1 - Overview", False),
    ("1.1.4 The fourth subtopic", False),
    ("10-12-2023", False),
    ("12.03.2021", False),
    ("Seite 123a", False),
    ("Seite1", False),
    ("pages 1-10", False),
    ("1.2.3 Section title", False),
    ("§3.4.5 Legal reference", False),
    ("1.1 Figures and Tables", False),
    ("Part 2: The Journey", False),
    ("Section 12.5", False),
    ("Chapter 1.1", False),
    ("Lesson 5: The Basics", False),
    ("1a. Introduction", False),
    ("12% of the population", False),
    ("100m race", False),
    ("5-star hotel", False),
    ("3D printing", False),
    ("Version 2.1.0", False),
    ("Phone: +1 (555), 123-4567", False),
    ("PageRank Algorithm", False),
    ("1st place winner", False),
    ("3-point shot", False),
    ("Stage 4 cancer", False),
    ("50 shades of grey", False),
    ("12 Angry Men", False),
    ("5-star rating", False),
    ("A4 paper size", False),
    ("IPv4 address", False),
    ("10 Downing Street", False),
    ("Step 1: Prepare materials", False),
    ("Rule 5: Be consistent", False),
    ("Area 51", False),
    ("8-bit processor", False),
    ("2D barcode", False),
    ("4096-bit encryption", False),
    ("21st Century Skills", False),
    ("Title: Example Title", False),
    ("ISBN: 978-3-16-148410-0", False),
    ("DOI: 10.1000/xyz123", False),
    ("Formula: a^2 + b^2 = c^2", False),
    ("Date: 01/01/2023", False),
    ("2023-04-03", False),
    ("Note: This is important", False)
    ]

    length_test_weight = 0.7
    onlynumbers_test_weight = 0.5
    out_of_x_test_weight = 0.3
    out_of_x_test_weight2 = 0.55
    page_indicator_test_weight = 0.65
    date_test_weight = -0.19
    weights = [
    length_test_weight,
    onlynumbers_test_weight,
    out_of_x_test_weight,
    out_of_x_test_weight2,
    page_indicator_test_weight,
    date_test_weight
    ]
    # Iterate until all test cases pass
    iteration = 0
    prev_failures1 = float('inf')
    prev_failures2 = float('inf')
    prev_weights1 = weights
    prev_weights2 = weights
    increasing_failures = 0
    iterations_since_last_decrease = 0
    weights_100_iterations_ago = weights
    best_weights = weights
    best_failures = float('inf')

    while True:
        iteration += 1
        if iteration % 10 == 0:
            print(f"Iteration {iteration}:")
        failures, new_weights = run_all_tests(test_cases, weights)
        if iteration % 10 == 0:
            print(f"Failures: {failures}")

        if failures < prev_failures1 - 1:
            prev_weights2 = prev_weights1
            prev_failures2 = prev_failures1
            prev_weights1 = weights
            prev_failures1 = failures
            weights = new_weights
            increasing_failures = 0
            iterations_since_last_decrease = 0
            weights_100_iterations_ago = weights
            if failures < best_failures:
                best_failures = failures
                best_weights = weights
        elif failures > prev_failures1:
            increasing_failures += 1
            if increasing_failures >= 2:
                weights = prev_weights2
                increasing_failures = 0
            else:
                prev_weights2 = prev_weights1
                prev_failures2 = prev_failures1
                prev_weights1 = weights
                prev_failures1 = failures
        else:
            weights = new_weights

        iterations_since_last_decrease += 1

        if iterations_since_last_decrease >= 100:
            weights = best_weights
            iterations_since_last_decrease = 0
            print("Resetting weights after 100 iterations without any decrease")

        if failures == 0:
            break

    print("All tests passed!")
    print("Final weights:", weights)



LIMIT_PAGE_NUMBER_LENGTH = 23
def detect_page_number(line):
    #print("weights: ", weights)
    # Returns True if the line is a page reference, otherwise returns False, using heuristics.

    
    length_test_weight = 0.9
    not_starting_with_number_test_weight = -0.35
    out_of_x_test_weight = 0.9
    out_of_x_slash_test_weight = 0.9
    out_of_x_test_weight2 = 0.9
    out_of_x_explicit_test_weight = 0.62
    page_indicator_test_weight = 0.65
    no_page_indicator_test_weight = -0.96
    date_test_weight_dateutil = -0.8
    date_test_weight_dateparser = -0.16
    #length_test_weight = weights[0]
    #out_of_x_test_weight = weights[2]
    #out_of_x_test_weight2 = weights[3]
    #page_indicator_test_weight = weights[4]
    #date_test_weight = weights[5]
    values = []
    reason = ""
    total_probability = 0.0
    page_indicators = [
    "Seite", "S\.", "S", "page", "Pagina", "Página", "p\.", "p", "pg", "strana", "stránka", "sivu", "oldal",
    "pág\.", "pág", "folio", "bladzijde", "страница", "ст\.", "ст",
    "sayfa", "صفحة", "עמוד", "ページ", "頁", "页", "sid\.", "sid", "str\.", "str", "sida", "sida\.",
    "стор\.", "стор", "Стр.", "Стр", "σελ\.", "σελ", "صفحه", "דף", "篇", "頁次", "페이지"
    ]

    # If a line is short - under 23 characters without whitespace, and ends with a number, it is most likely a page reference.
    if len(''.join(line.split())) < LIMIT_PAGE_NUMBER_LENGTH and re.match(r".*\d$", ''.join(line.split())):
        total_probability += length_test_weight
        values.append(length_test_weight)
        reason = reason + "length\n"
    else:
        values.append(0)

    # If a line does not start with a number, it is less likely a page reference.
    not_starting_with_number_pattern = "^[^0-9].*"
    if re.match(not_starting_with_number_pattern, line):
        total_probability += not_starting_with_number_test_weight
        values.append(not_starting_with_number_test_weight)
        reason = reason + "not_starting_with_number\n"
    else:
        values.append(0)

    # If a line contains only numbers and whitespace (also roman numerals between 1 and 30), consider it a page reference.
    if all(c.isdigit() or c.isspace() for c in line) or re.match(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$", ''.join(line.split()), re.I):
        return True
    else:
        values.append(0)

    # If a line contains something like "1/10" it is probably a page reference.
    out_of_x_pattern = ".*[0-9]{1,5}\s*\/\s*[0-9]{1,5}"
    if re.match(out_of_x_pattern, line):
        total_probability += out_of_x_test_weight
        values.append(out_of_x_test_weight)
        reason = reason + "outofx\n"
    else:
        values.append(0)

    # If a line contains explicitly something like "1/10" with forward-slash it is probably a page reference.
    out_of_x_slash_pattern = "^[0-9]{1,5}/[0-9]{1,5}$"
    if re.match(out_of_x_slash_pattern, line):
        total_probability += out_of_x_slash_test_weight
        values.append(out_of_x_slash_test_weight)
        reason = reason + "outofx-slash\n"
    else:
        values.append(0)

    # If a line contains something like "1 of 10" it is probably a page reference.
    out_of_x_pattern2 = ".*[0-9]{1,5}\s+[^0-9]*\s+[0-9]{1,5}$"
    if re.match(out_of_x_pattern2, line):
        total_probability += out_of_x_test_weight2
        values.append(out_of_x_test_weight2)
        reason = reason + "outofx2\n"
    else:
        values.append(0)

    # If a line contains exact " of [number]", it's even more likely a page reference.
    out_of_x_explicit_pattern2 = ".* of [0-9]"
    if re.match(out_of_x_explicit_pattern2, line, flags=re.I):
        total_probability += out_of_x_explicit_test_weight
        values.append(out_of_x_explicit_test_weight)
        reason = reason + "outofx-explicit\n"
    else:
        values.append(0)

    # If the line contains a page indicator, it is probably a page reference.
    # Iterate over all page indicators and check if the line contains one of them together with a number, at the end of the line.
    word_found = False
    for word in page_indicators:
        pattern = fr"(?:^|[^a-zA-Z]){word}\s*[0-9]+.*$"
        if re.search(pattern, line, flags=re.I):
            total_probability += page_indicator_test_weight
            values.append(page_indicator_test_weight)
            word_found = True
            reason = f"{reason}pageindicator {word}\n"
            break
    if not word_found:
        total_probability += no_page_indicator_test_weight
        reason = reason + "NOpage-indicator\n"
        values.append(no_page_indicator_test_weight)

    # If text contains something that can be interpreted as a date, it might not be a page reference.
    try:
        date = parser.parse(line)
        total_probability += date_test_weight_dateutil
        values.append(date_test_weight_dateutil)
        reason = reason + "date: " + str(parser.parse(line))
    except ValueError:
        values.append(0)
        pass

    # If text contains something that can be interpreted as a date, it might not be a page reference.
    if dateparser.parse(line):
        total_probability += date_test_weight_dateparser
        values.append(date_test_weight_dateparser)
        reason = reason + "date: " + str(dateparser.parse(line))
    else:
        values.append(0)

    print(reason)
    print(f"{values} - Summe: {str(sum(values))}")
    #print(total_probability)
    if round(total_probability, 2) >= 0.5:
        return True#, values
    else:
        return False#, values

def run_test_detect_page_number(string, expected):
    print(f"Testing {string}:")
    result = detect_page_number(string)
    if result == expected:
        print("Test passed")
    else:
        print("Test failed")
        print(f"Expected {expected}, got {result}")
        raise Exception("Test failed")
    print("-" * 20)

def test_detect_page_number():
    # Unit tests of detect_page_number
    # Positive tests (expect True)
    print("Starting tests")
    run_test_detect_page_number("Seite 1", True)
    run_test_detect_page_number("Seite 1/10", True)
    run_test_detect_page_number("Seite 1 of 10", True)
    run_test_detect_page_number("Seite 1 von 10", True)
    run_test_detect_page_number("Seite 1", True)
    run_test_detect_page_number("  S. 10  ", True)
    run_test_detect_page_number("  page 5", True)
    run_test_detect_page_number("p.3", True)
    run_test_detect_page_number("pg 123", True)
    run_test_detect_page_number("1/10", True)
    run_test_detect_page_number("2 of 20", True)
    run_test_detect_page_number("3 out of 30", True)
    run_test_detect_page_number("1/5", True)
    run_test_detect_page_number("Page 6 of 12", True)
    run_test_detect_page_number("1 of 10", True)
    run_test_detect_page_number("   123 ", True)
    run_test_detect_page_number("P 1", True)
    run_test_detect_page_number("página 7", True)
    run_test_detect_page_number("страница 42", True)
    run_test_detect_page_number("σελ. 15", True)
    run_test_detect_page_number("עמוד 22", True)
    run_test_detect_page_number("ページ 36", True)
    run_test_detect_page_number("stránka 11", True)
    run_test_detect_page_number("sivu 9", True)
    run_test_detect_page_number("oldal 17", True)
    run_test_detect_page_number("Página 14", True)
    run_test_detect_page_number("Folio 8", True)
    run_test_detect_page_number("bladzijde 24", True)
    run_test_detect_page_number("sayfa 20", True)
    run_test_detect_page_number("صفحة 18", True)
    run_test_detect_page_number("頁 31", True)
    run_test_detect_page_number("页 21", True)
    run_test_detect_page_number("str. 13", True)
    run_test_detect_page_number("sida 10", True)
    run_test_detect_page_number("Стр. 27", True)
    run_test_detect_page_number("페이지 28", True)
    run_test_detect_page_number("Seite1", True)
    run_test_detect_page_number("Страница 2", True)
    run_test_detect_page_number("Pagina 3", True)
    run_test_detect_page_number("ページ 1", True)
    run_test_detect_page_number("Pagina 9", True)
    run_test_detect_page_number("s. 11", True)
    run_test_detect_page_number("S. 7", True)
    run_test_detect_page_number("Page 4", True)
    run_test_detect_page_number("Página 6", True)
    run_test_detect_page_number("sayfa 8", True)
    run_test_detect_page_number("페이지 5", True)
    run_test_detect_page_number("pagina 12", True)
    run_test_detect_page_number("страница 6", True)
    run_test_detect_page_number("Section 1.1 - Page 5", True)

    # Negative tests (expect False)
    run_test_detect_page_number("a. 1", False)
    run_test_detect_page_number("1 of 3 steps", False)
    run_test_detect_page_number("3 out of 4 participants", False)
    run_test_detect_page_number("2/5 progress", False)
    run_test_detect_page_number("Grade: 5/5", False)
    run_test_detect_page_number("1st of April", False)
    run_test_detect_page_number("9th of 12 items", False)
    run_test_detect_page_number("A 1:5 scale model", False)
    run_test_detect_page_number("A 1/2 share", False)
    run_test_detect_page_number("50/50 chance", False)
    run_test_detect_page_number("12.5% interest rate", False)
    run_test_detect_page_number("1:1 support", False)
    run_test_detect_page_number("3/4 completed", False)
    run_test_detect_page_number("1.5 times larger", False)
    run_test_detect_page_number("F. 32", False)
    run_test_detect_page_number("b. 6", False)
    run_test_detect_page_number("4 of 4 apples", False)
    run_test_detect_page_number("2 out of 3 books", False)
    run_test_detect_page_number("5 out of 5 stars", False)
    run_test_detect_page_number("7 of 7 lessons", False)
    run_test_detect_page_number("1 in 10 chance", False)
    run_test_detect_page_number("3/4 cup of sugar", False)
    run_test_detect_page_number("June 1 of 2022", False)
    run_test_detect_page_number("Date: 01/01/2023", False)
    run_test_detect_page_number("Introduction", False)
    run_test_detect_page_number("Chapter 1: The Beginning", False)
    run_test_detect_page_number("Section 1.1 - Overview", False)
    run_test_detect_page_number("1.1.4 The fourth subtopic", False)
    run_test_detect_page_number("10-12-2023", False)
    run_test_detect_page_number("12.03.2021", False)
    run_test_detect_page_number("Seite 123a", False)
    run_test_detect_page_number("pages 1-10", False)
    run_test_detect_page_number("1.2.3 Section title", False)
    run_test_detect_page_number("§3.4.5 Legal reference", False)
    run_test_detect_page_number("1.1 Figures and Tables", False)
    run_test_detect_page_number("Part 2: The Journey", False)
    run_test_detect_page_number("Section 12.5", False)
    run_test_detect_page_number("Chapter 1.1", False)
    run_test_detect_page_number("Lesson 5: The Basics", False)
    run_test_detect_page_number("1a. Introduction", False)
    run_test_detect_page_number("12% of the population", False)
    run_test_detect_page_number("100m race", False)
    run_test_detect_page_number("5-star hotel", False)
    run_test_detect_page_number("3D printing", False)
    run_test_detect_page_number("Version 2.1.0", False)
    run_test_detect_page_number("Phone: +1 (555) 123-4567", False)
    run_test_detect_page_number("PageRank Algorithm", False)
    run_test_detect_page_number("1st place winner", False)
    run_test_detect_page_number("3-point shot", False)
    run_test_detect_page_number("Stage 4 cancer", False)
    run_test_detect_page_number("50 shades of grey", False)
    run_test_detect_page_number("12 Angry Men", False)
    run_test_detect_page_number("5-star rating", False)
    run_test_detect_page_number("A4 paper size", False)
    run_test_detect_page_number("IPv4 address", False)
    run_test_detect_page_number("10 Downing Street", False)
    run_test_detect_page_number("Step 1: Prepare materials", False)
    run_test_detect_page_number("Rule 5: Be consistent", False)
    run_test_detect_page_number("Area 51", False)
    run_test_detect_page_number("8-bit processor", False)
    run_test_detect_page_number("2D barcode", False)
    run_test_detect_page_number("4096-bit encryption", False)
    run_test_detect_page_number("21st Century Skills", False)
    run_test_detect_page_number("Title: Example Title", False)
    run_test_detect_page_number("ISBN: 978-3-16-148410-0", False)
    run_test_detect_page_number("DOI: 10.1000/xyz123", False)
    run_test_detect_page_number("Formula: a^2 + b^2 = c^2", False)
    run_test_detect_page_number("2023-04-03", False)
    run_test_detect_page_number("Note: This is important", False)

def extract_sections(text):
    # Split the text into lines
    lines = text.splitlines()
    if text == "":
        return {}
    # Initialize variables
    text_sections = {}
    section_index = 0
    skip_count = 0
    continue_previous = False

    # Check if there are no headlines in the text
    if not any(re.match(heading_pattern, line) for line in lines) or all(detect_page_number(line) for line in lines):
        headline = TEXT_WITHOUT_ANY_HEADLINES
        text_content = text
        while len(text_content.strip()) > MAX_VECTOR_LENGTH:
            text_sections[section_index] = (headline, text_content[:MAX_VECTOR_LENGTH].strip())
            section_index += 1
            text_content = text_content[MAX_VECTOR_LENGTH:]
        text_sections[section_index] = (headline, text_content.strip())
        return text_sections

    # Iterate through the lines
    for i in range(len(lines)):
        if skip_count > 0:  # Skip this iteration if necessary
            skip_count -= 1
            continue

        if detect_page_number(lines[i]): # It's a page number/page reference
            continue_previous = True
            continue

        # Check if the current line is a headline
        if re.match(heading_pattern, lines[i]):
            headline = lines[i]
            text_content = ""

            # Check if we should continue the previous section
            if continue_previous:
                headline = NOHEADLINE
                continue_previous = False

            j = i + 1
            while j < len(lines) and not re.match(heading_pattern, lines[j]):  # Collect text lines until the next headline
                text_content += lines[j] + "\n"
                j += 1

            # Check if we can combine multiple headlines
            if len(text_content.strip()) <= CHAR_PER_SECTION:
                next_headlines_combined = ""

                while (j + 1) < len(lines) and len(next_headlines_combined + lines[j] + "\n" + lines[j+1]) <= CHAR_PER_SECTION:
                    next_headlines_combined += lines[j] + "\n" + lines[j+1] + "\n"
                    j += 2
                    skip_count += 2

                text_content += next_headlines_combined

            # Check if the text_content is larger than MAX_VECTOR_LENGTH
            while len(text_content.strip()) > MAX_VECTOR_LENGTH:
                text_sections[section_index] = (headline, text_content[:MAX_VECTOR_LENGTH].strip())
                section_index += 1
                text_content = text_content[MAX_VECTOR_LENGTH:]
                headline = NOHEADLINE

            # Store the section
            text_sections[section_index] = (headline, text_content.strip())
            section_index += 1

    return text_sections

longtext = """"Historischer Überblick
Eine explizit sozialistische Bewegung entwickelte sich erst infolge von Aufklärung und industrieller Revolution zwischen Ende des 18. Jahrhunderts und Mitte des 19. Jahrhunderts. Sie war eng verwoben mit der Entstehung der Arbeiterbewegung. Wie bei allen -ismen trat der Sozialismus historisch in vielfältigen Formen auf: von den genossenschaftlichen Ideen der Frühsozialisten über die parteipolitische Organisation in sozialdemokratischen, sozialistischen und danach kommunistischen Parteien, die im Verlauf des 20. Jahrhunderts oft unterschiedliche Ausprägungen annahmen. Seite 12

Frühsozialismus
→ Hauptartikel: Frühsozialismus
Frühsozialisten wie François Noël Babeuf, Claude-Henri Comte de Saint-Simon, Louis-Auguste Blanqui, Charles Fourier, Pierre-Joseph Proudhon, William Godwin, Robert Owen oder Moses Hess legten politische Konzepte von quasi-absolutistischen Diktaturen bis hin zu einem anarchistischen Föderalismus vor. Einig waren sie sich einerseits in einer abwehrenden Reaktion gegen Effekte des Frühkapitalismus wie in der Hoffnung auf eine Gesellschaft, die mittelalterliche Standesunterschiede ebenso überwinden würde wie neuere Klassengegensätze. Oftmals argumentierten sie sehr moralisch. Eine sozialwissenschaftlich inspirierte Analyse, wie sie von Karl Marx geleistet wurde, gab es noch nicht.

Sozialstrukturell gesehen wurde der Frühsozialismus nicht von der Arbeiterklasse getragen, sondern von Handwerkern und Kleinbürgertum. Diese begannen bereits die Verwerfungen der industriellen Revolution zu spüren, ohne dass es schon zur Bildung eines Industrieproletariats gekommen wäre.

Einige wie Robert Owen versuchten den Aufbau abgeschlossener sozialistischer Gemeinschaften in einer so empfundenen feindlichen Umwelt. Die meisten Sozialisten zielten auf eine grundlegende Veränderung der gesamten Gesellschaft.

Sozialistisch inspirierte Aktivisten beteiligten sich an der französischen Revolution von 1789 bis 1799 und an den im Wesentlichen als bürgerlich geltenden europäischen Revolutionen bis 1848/1849 (siehe Julirevolution 1830, Februarrevolution 1848 und Märzrevolution 1848/1849); einen letzten Höhepunkt im 19. Jahrhundert hatten diese frühsozialistischen Bewegungen in der Pariser Kommune von 1871, die als erste proletarische Revolution gilt und die schon nach kurzer Zeit blutig niedergeschlagen wurde.

Durch die historische Entwicklung bedingt wurden die Diskussionslinien danach klarer: Die vielfältigen Ansätze des Frühsozialismus spalteten sich in drei Hauptlinien, den Anarchismus und die vom Marxismus inspirierten kommunistischen und sozialdemokratischen Bewegungen. Vereinzelt, wie im 20. Jahrhundert bei den russischen Revolutionen von 1905 und der Februarrevolution 1917 (bei der Oktoberrevolution 1917 nur noch sehr bedingt), der Münchner Räterepublik 1919 oder dem Spanischen Bürgerkrieg 1936 bis 1939 kam es zur Zusammenarbeit der drei Gruppen. Diese war jedoch jeweils nur kurzfristig, meist von heftigen internen Auseinandersetzungen geprägt und endete im Sieg einer Gruppe oder der Niederlage aller.
Seite 13

Anarchismus
→ Hauptartikel: Anarchismus, Kommunistischer Anarchismus und Anarchosyndikalismus

Louise Michel (1830–1905) war eine bedeutende Exponentin des Anarchismus
Auch die Anarchisten verstanden sich in sozialistischer Tradition:

„Was im Juni 1848 unterlag, war nicht der Sozialismus im Allgemeinen, nur der Staatssozialismus, der autoritäre und reglementmäßige Sozialismus, der geglaubt und gehofft hatte, dass der Staat den Bedürfnissen und legitimen Wünschen der Arbeiterklasse volle Befriedigung gewähren werde und mit seiner Allmacht eine neue soziale Ordnung einführen wolle und könne.“[18]

Die Theorie des Anarchismus lehnt daher staatliche Strukturen als Herrschaftsinstrument ab. Der Anarchismus baut auf die freiwillige Verbindung der Individuen in Kollektiven, Räten und Kommunen, um dieselben Ziele zu erreichen. Der Anarchismus strebt eine Synthese zwischen individueller Freiheit und kollektiver Verantwortung an und unterscheidet sich von den autoritären Strömungen. Statt des Staates wird beispielsweise von Bakunin vorgeschlagen:

„Die Gesellschaft so zu organisieren, dass jedes auf die Welt kommende männliche oder weibliche Wesen ungefähr gleiche Mittel zur Entwicklung seiner Fähigkeiten und ihrer Nutzbarmachung durch die Arbeit vorfindet…“[19]
Seite 14

Religiös motivierte Sozialisten
→ Hauptartikel: Religiöser Sozialismus

Wilhelm Weitling (1805–1871) begründete sozialistische Positionen unter Bezugnahme auf das christliche Gleichheitsideal
Die Bewegung des Religiösen Sozialismus entstand mit der erstarkenden Arbeiterbewegung in Mitteleuropa seit dem 19. Jahrhundert vor allem unter sozial engagierten Christen, zum Teil auch Juden.

Dass der Sozialismus, der den demokratischen Radikalismus der deutschen Handwerker, Arbeiter und Intellektuellen ablöste, sich als religiöser Sozialismus konstituierte, ist entscheidend auf den Schneidergesellen Wilhelm Weitling, das Haupt der Bewegung zu Beginn der 1840er Jahre, zurückzuführen. Seine sozialistische, am Ideal der Gütergemeinschaft orientierte Gesellschaftsutopie begründete Weitling in der Schrift Die Menschheit wie sie ist und sein sollte 1839/40, aber auch noch in seinem Evangelium eines armen Sünders 1843 überwiegend christlich-religiös.[20][21]

Besonders seit der Erfahrung des Ersten Weltkriegs gewann unter Juden die Überzeugung an Boden, dass dauerhafter Frieden entsprechend der Tora und dem Evangelium nur verwirklicht werden könne, wenn der auf Egoismus, Konkurrenz und Ausbeutung gegründete Kapitalismus überwunden werde.

Hermann Samuel Reimarus, Karl Kautsky, R. Eisler, Samuel George Frederick Brandon, und andere beriefen sich in ihrem „sozialen und politischen Kampf gegen bestehende Ordnungen“ auf Person und Handeln Jesu, und betonten seine Nähe zur Bewegung der Zeloten.[22]

Andere wie z. B. der Theologe Hans Küng, halten eine Inanspruchnahme Jesu für sozialrevolutionäre Bestrebungen für konstruiert.[23]
Seite 15

Marxistischer Sozialismus

Karl Marx, vor 1875
Laut Friedrich Engels bedeutete Sozialismus noch 1847 eine Bourgeoisbewegung, Kommunismus indes eine Arbeiterbewegung (Cabet, Weitling), weswegen Karl Marx und Engels damals noch der Bezeichnung „Kommunisten“ den Vorzug gaben. Erst 1887 bekannten sich sogar die englischen Gewerkschaften zum Sozialismus.[24]

Der Marxismus hatte lange Zeit die Deutungshoheit in der sozialistischen Bewegung. Nach dem Verfall der ersten Internationale 1876 bis über den größten Teil des gesamten 20. Jahrhunderts hinweg wurden Diskussionen innerhalb des und über den Sozialismus überwiegend mit den von Marx und Engels geprägten Begriffen geführt.

Marx und Engels betrachteten den Frühsozialismus als Utopischen Sozialismus und stellten ihm den wissenschaftlichen Sozialismus gegenüber. Nach der Theorie von Marx und Engels stehen sich in der Epoche des Kapitalismus die Kapitalistenklasse (Privateigentümer auf Produktionsmittel) und die Arbeiterklasse (Proletariat) als Gegenspieler gegenüber. Die Arbeiter seien gezwungen ihre Arbeitskraft an die Kapitalisten zu verkaufen. Der jeweilige Kapitalist stelle die Arbeiter als Lohnabhängige ein und profitiere von deren Arbeit, weil er den Arbeitern immer nur einen Teil des durch ihre Arbeit erwirtschafteten Geldes auszahle, den Rest behalte er für sich. Demnach entstehe Ausbeutung. Die verschiedenen Interessen der beiden Klassen würden sich in einem stetigen Widerstreit befinden, also in einem Klassenkampf. Die Zuspitzung dieses Widerstreits würde es nach Marx und Engels erforderlich machen, dass die organisierte Arbeiterklasse die Macht erobern müsse, um sich selbst zu befreien.[25] Nach Marx ist die Diktatur des Proletariats mit ihrer Aufgabe die Aufhebung des Privateigentums an Produktionsmitteln die Voraussetzung der klassenlosen Gesellschaft (Kommunismus). Nach Friedrich Engels wird diese Diktatur eine demokratische Herrschaft der Mehrheit über die Reste der Ausbeuterklasse sein. Marx und er forderten Verstaatlichungen aller Produktionsmittel, zum Beispiel im Manifest der Kommunistischen Partei:

„Das Proletariat wird seine politische Herrschaft dazu benutzen, der Bourgeoisie nach und nach alles Kapital zu entreißen, alle Produktionsinstrumente in den Händen des Staats, d. h. des als herrschende Klasse organisierten Proletariats, zu zentralisieren und die Masse der Produktionskräfte möglichst rasch zu vermehren.“[26]

Wie die Gesellschaftsform nach der Entwicklung vom Sozialismus zum Kommunismus, also der klassenlosen Gesellschaft, genauer aussehen werde, wurde von Marx und Engels bewusst nicht genauer ausgemalt und werde sich der Theorie folgend anhand konkreter gesellschaftlicher Entwicklungen und Widersprüche zeigen.

Zwei bekannte Zitate, die sich um die Entwicklung zur höheren Phase der kommunistischen Gesellschaft drehen:

„In einer höheren Phase der kommunistischen Gesellschaft, nachdem die knechtende Unterordnung der Individuen unter die Teilung der Arbeit, damit auch der Gegensatz geistiger und körperlicher Arbeit verschwunden ist; nachdem die Arbeit nicht nur Mittel zum Leben, sondern selbst das erste Lebensbedürfnis geworden; nachdem mit der allseitigen Entwicklung der Individuen auch ihre Produktivkräfte gewachsen und alle Springquellen des genossenschaftlichen Reichtums voller fließen – erst dann kann der enge bürgerliche Rechtshorizont ganz überschritten werden und die Gesellschaft auf ihre Fahne schreiben: Jeder nach seinen Fähigkeiten, jedem nach seinen Bedürfnissen!“[27]

„Sobald es keine Gesellschaftsklasse mehr in der Unterdrückung zu halten gibt, sobald mit der Klassenherrschaft und dem in der bisherigen Anarchie der Produktion begründeten Kampf ums Einzeldasein auch die daraus entspringenden Kollisionen und Exzesse beseitigt sind, gibt es nichts mehr zu reprimieren, das eine besondre Repressionsgewalt, einen Staat, nötig machte. Der erste Akt, worin der Staat wirklich als Repräsentant der ganzen Gesellschaft auftritt – die Besitzergreifung der Produktionsmittel im Namen der Gesellschaft, ist zugleich sein letzter selbständiger Akt als Staat. Das Eingreifen einer Staatsgewalt in gesellschaftliche Verhältnisse wird auf einem Gebiete nach dem andern überflüssig und schläft dann von selbst ein. An die Stelle der Regierung über Personen tritt die Verwaltung von Sachen und die Leitung von Produktionsprozessen. Der Staat wird nicht ‚abgeschafft‘, er stirbt ab.“[28]
Seite 16

Die Phase der Diktatur wurde von Wladimir Iljitsch Lenin als eigenständige Gesellschaftsformation verstanden, die er als Sozialismus bezeichnete. In ihr würden die Proletarier die Produktionsverhältnisse durch Vergesellschaftung der Produktionsmittel so verändern, dass schließlich die Klassengegensätze selbst aufgehoben würden. Der Staat, von Marx als Instrument der Unterdrückung einer Klasse durch die andere gedacht, werde somit überflüssig und sterbe ab, woraus die letzte Gesellschaftsformation der Menschheitsgeschichte möglich werde, der Kommunismus.[29]

Im sogenannten Revisionismusstreit innerhalb der deutschen Sozialdemokratie grenzten sich Marxisten, die auf eine Revolution setzten, von solchen ab, die den Sozialismus auf dem Wege von Reformen herbeiführen wollten. Rosa Luxemburg betonte hierbei die Unumgänglichkeit der Revolution, indem sie zum Beispiel schrieb:

„Für die Sozialdemokratie besteht zwischen der Sozialreform und der sozialen Revolution ein unzertrennlicher Zusammenhang, indem ihr der Kampf um die Sozialreform das Mittel, die soziale Umwälzung aber der Zweck ist.“[30]

Ihr parteiinterner Gegner Eduard Bernstein vertrat die Ansicht, die Sozialdemokratie könne die angestrebte grundlegende Erneuerung der Gesellschaft durch einen beständigen Reformprozess erreichen. Er stellte die Notwendigkeit der proletarischen Revolution in Frage und propagierte die Teilhabe am politischen System des Kaiserreiches. In der Weimarer Republik und den ersten zwanzig Jahren der Bundesrepublik wurde diese Differenzierung durchgehalten.
Seite 17

Realsozialismus
→ Hauptartikel: Realsozialismus

Sowjetisches Lenindenkmal in Ulan-Ude
Als real existierenden Sozialismus bezeichneten sich jene Staaten, die seit 1917 von einer Kommunistischen Partei, in der Regel in einem Ein-Parteien-System, regiert wurden: besonders die Sowjetunion mit der KPdSU und die ab 1945 an ihrem System ausgerichteten Staaten des europäischen „Ostblocks“, darunter: Polen, ČSSR, Ungarn, Bulgarien, Rumänien, Deutsche Demokratische Republik sowie die Mongolische Volksrepublik. Weiterhin bestehen bis heute einige weitere sehr unterschiedliche, sich teilweise widersprechende von manchen als realsozialistisch bezeichnete Systeme wie die Volksrepublik China (seit 1949), im nach dem Vietnamkrieg vereinigten Vietnam (spätestens seit 1975), Laos (seit 1975), Kuba (seit 1959) oder Nordkorea (seit 1948).

Mit der Oktoberrevolution 1917 in Russland sollten die Ideen des Sozialismus erstmals in einem großen Flächenstaat in die Praxis umgesetzt werden. Der Begriff des Realsozialismus sollte erklären, warum viele Vorhersagen der marxschen Theorie wie die Weltrevolution und die rasche Entwicklung größeren Wohlstands in den sozialistischen Staaten nicht eintraten und diese Staaten sich dennoch weiter zum Kommunismus entwickelten, allerdings mit Problemen der Realpolitik zu kämpfen hatten.

Stalin vertrat nach Lenins Tod die Theorie vom möglichen „Sozialismus in einem Land“, der sich unabhängig von der Weltrevolution etablieren und halten könne. Trotzki stellte dagegen seine Theorie der permanenten Revolution auf, um bürokratische Erstarrung einer Sozialrevolution durch erneute innenpolitische Umwälzungen und Revolutionierung weiterer Länder zu verhindern. Nachdem sich Stalin gegen Trotzki durchgesetzt hatte, gab die von ihm beherrschte KP die ursprünglichen Ziele auch der Bolschewiki auf, die eine Demokratisierung nach erfolgreichem Aufbau sozialistischer Produktionsverhältnisse in Aussicht gestellt hatten. Stalins rigorose Zwangsmaßnahmen zur forcierten Industrialisierung, Kollektivierung der Landwirtschaft, ethnischen Homogenisierung und Ausschaltung jeder möglichen Opposition – zusammengefasst als Stalinismus – aber auch die ähnliche Politik seiner Nachfolger und die ständigen schweren Verstöße gegen die Menschenrechte in realsozialistischen Staaten haben diese Systeme weltweit diskreditiert. Die faktisch nationale, diktatorisch-technokratische Machtpolitik und das imperialistische Hegemoniestreben solcher Staaten gefährdete aus Sicht vieler Kritiker alle weiteren Anläufe zu einem von der Sowjetunion oder China unabhängigen Sozialismus. Realsozialismus wird dabei entweder als logische Konsequenz des marxschen Sozialismusmodells oder als dessen Verkehrung ins Gegenteil kritisiert, sodass viele Kritiker diesen Staaten das Recht absprachen, sich sozialistisch zu nennen.

	
Teile dieses Abschnitts scheinen seit einigen Jahren nicht mehr aktuell zu sein.
Bitte hilf uns dabei, die fehlenden Informationen zu recherchieren und einzufügen.
	
Dieser Artikel oder nachfolgende Abschnitt ist nicht hinreichend mit Belegen (beispielsweise Einzelnachweisen) ausgestattet. Angaben ohne ausreichenden Beleg könnten demnächst entfernt werden. Bitte hilf Wikipedia, indem du die Angaben recherchierst und gute Belege einfügst.
Seit der Wende und friedlichen Revolution von 1989 gilt der Realsozialismus trotz einiger noch bestehender Systeme dieser Art als historisch gescheitert. Als Hauptursachen für das Scheitern des Realsozialismus sehen viele folgende Entwicklungen:

Entgegen den Voraussagen des Marxismus entwickelten die kapitalistisch geprägten Industriestaaten Europas, Nordamerikas und Ostasiens auf Druck der Arbeiterbewegung und der Konkurrenz des Realsozialismus ein mehr oder weniger stark ausgeprägtes soziales Sicherungssystem in einem Sozialstaat, der die schlimmsten sozialen Unterschiede und die Armut in diesen Ländern abfederte und somit auch das revolutionäre Potenzial dort deutlich minimierte.
Der Staatsapparat der meisten realsozialistischen Staaten erwies sich aufgrund mangelnder demokratischer Mitbestimmung als zunehmend unflexibel, und aufgrund ideologischer und anderer Hemmnisse kaum fähig, mit dem Komplexitätsgrad moderner westlicher Gesellschaften umzugehen.
Seite 18
Die Staaten des realen Sozialismus orientierten sich an einem in der Regel kapitalistisch geprägten Modernisierungsmodell, nur konnten sie den Grad der Modernisierung dieser Staaten, von wenigen technologischen Ausnahmen abgesehen, kaum aufholen. Sie versuchten trotzdem – etwa durch Subventionen in vielen Bereichen (Gesundheitswesen, öffentlicher Verkehr, Grundnahrungsmittelproduktion, Wohnungsbau usw.) – die Forschungsleistungen der kapitalistischen Staaten zu übertreffen, was in der Losung „Überholen, ohne einzuholen“[31][32] zusammengefasst wurde.
Die politischen Systeme realsozialistischer Staaten wurden auf Dauer nur selten von der Mehrheit der jeweiligen Bevölkerung getragen, insbesondere dort nicht, wo das entsprechende System (ohne eigene Revolution) von außen aufgezwungen wurde (vor allem in Ungarn, der ČSSR, Rumänien, Polen, der DDR und Bulgarien). Diese Systeme wurden gegen eine sich regende Opposition von den herrschenden sozialistischen oder kommunistischen Parteien auf Dauer auch durch einen zunehmend ausufernden Polizeistaat (Bespitzelung, Repressionen, Zensur) am Leben erhalten. Der unwillige Teil der Bevölkerung, der zum Teil lieber ausgewandert wäre, wurde oft durch Sperranlagen und strenge Visa-Bestimmungen am Verlassen des Staates gehindert. Realsozialistische Staaten setzten auch Mittel ein, unter denen die Verfechter des Sozialismus im 19. Jahrhundert gelitten hatten, beispielhaft hierfür ist die politische Verfolgung von Trotzkisten.
Der in den meisten realsozialistischen Staaten umgesetzten staatlich und zentral gelenkten Planwirtschaft fehlte es oft an Übersicht über die Bedingungen und den Bedarf vor Ort. Durch langfristige wirtschaftliche Planung ohne eine Rückmeldung von den Produzenten und Konsumenten ging oft die Flexibilität verloren, kurzfristig auf komplexe Wirtschaftsvorgänge zu reagieren. Die Folge war, dass häufig am Bedarf vorbei produziert wurde, ökonomisch notwendige Investitionen unterblieben, Ressourcen unzweckmäßig eingesetzt und Innovationen nicht umgesetzt wurden. Eine weitere wirtschaftliche Ursache für das Scheitern des Realsozialismus war die hohe Verschuldung der entsprechenden Staaten, die insbesondere im Kalten Krieg zunahm, beispielsweise, um in der Rüstungsproduktion mit der militärischen Entwicklung der USA und der NATO Schritt zu halten (vgl. Wettrüsten).
Seite 19
Siehe auch: Liste sozialistischer Staaten
Sozialdemokratie
→ Hauptartikel: Sozialdemokratie

Eduard Bernstein (1850–1932) Vertreter des sozialdemokratischen Reformismus
In der europäischen Sozialdemokratie setzte sich seit etwa 1900 der Reformismus durch, der den Sozialismus nicht durch eine soziale Revolution, sondern durch demokratische Reformen erreichen zu können glaubt. Damit wurden sozialdemokratische Gründungsprogramme, die Sozialismus gemäß der marxschen Theorie vom Klassenkampf als Ergebnis krisenhafter Zuspitzungen der sozialen Gegensätze und revolutionärer Umgestaltungen erwarteten, zuerst in der praktischen Alltagspolitik und dann theoretisch aufgegeben.

In Deutschland begann die Auseinandersetzung um einen revolutionären oder reformistischen Weg zum Sozialismus mit Veröffentlichungen Eduard Bernsteins, die 1896 die Revisionismusdebatte auslösten. Zwar fand Bernsteins Position in der SPD zunächst keine Mehrheit, doch setzte sie sich nach dem Tod des Parteivorsitzenden August Bebel 1913 unter seinem Nachfolger Friedrich Ebert mehr und mehr durch. Hieraus und aus der Zustimmung der SPD-Reichstagsfraktion zu den Kriegsanleihen zur Finanzierung des Ersten Weltkriegs 1914, an dem die Sozialistische Internationale zerbrach, wurden ideologische Auseinandersetzungen innerhalb der Sozialdemokratie manifest, die schließlich zur Spaltung der SPD in USPD und MSPD führte. Sie verschärften sich seit der Oktoberrevolution in Russland 1917. Es kam zu einer Spaltung zwischen Sozialisten und Kommunisten, die eigene kommunistische Parteien gründeten. Der Bruch zwischen beiden Lagern zeigte sich besonders am Verhältnis zum sogenannten Realsozialismus sowjetischer Prägung. Die Anfang 1919 gegründete Kommunistische Partei Deutschlands (KPD) beanspruchte als Nachfolgerin des Spartakusbundes, mit dem proletarischen Internationalismus die besten sozialdemokratischen Traditionen zu bewahren. Mit der Ermordung der Spartakusführer und KPD-Gründer Rosa Luxemburg und Karl Liebknecht wurde die Spaltung der deutschen Arbeiterbewegung in die reformorientierte SPD und die marxistisch-revolutionäre KPD unumkehrbar, während die USPD bis 1922 zwischen diesen beiden Polen zerrieben wurde und danach keine bedeutende Rolle in der Weimarer Republik mehr spielte.

In Russland spaltete sich die Sozialdemokratie schon 1903 in die reformorientierten Menschewiki (= Minderheitler) und die marxistisch-revolutionären Bolschewiki (= Mehrheitler), deren Gegensatz nach vorübergehender neuer Zusammenarbeit 1912 endgültig wurde. Den Menschewiki gelang unter Kerenski mit der Februarrevolution 1917 der Sturz des Zaren und die Regierungsbildung, doch setzten sie den Krieg gegen Deutschland für Gebietsgewinne fort. Die theoretische, nach seiner Rückkehr aus dem Exil 1917 auch die praktische Führung der Bolschewiki übernahm Lenin. Durch das Angebot eines Sofortfriedens gewann er eine Mehrheit im Rätekongress, die er für eine erneute Revolution – diesmal gegen das russische Parlament in Petersburg – nutzte. Nach dem fünfjährigen Russischen Bürgerkrieg gegen verschiedene zarentreue „Weiße Truppen“ (vgl. Weiße Armee) gründeten die Bolschewiki die UdSSR mit der seit 1952 KPdSU genannten alleinherrschenden Staatspartei. Damit verlor die unterlegene russische Sozialdemokratie fast bis zum Ende der Sowjetunion 1990 jede machtpolitische Bedeutung.

Die innersozialistischen Gegensätze in der „Systemfrage“, die in Deutschland zugunsten der Reformisten, in Russland zugunsten der Leninisten ausgegangen waren, vertieften nach dem Rechtsruck der Weimarer Republik ab 1923 die Spaltung zwischen Sozialdemokraten und Kommunisten und schwächten so die Zukunftsperspektiven des Sozialismus weltweit. Obwohl die SPD bis zu ihrem Heidelberger Programm von 1925 am Ziel einer Ablösung der kapitalistischen durch eine sozialistische Wirtschaftsordnung festhielt, ging sie im politischen Alltag den Weg einer Reformpartei, die ihre Ziele parlamentarisch durch Kompromisse und Koalitionen – auch mit gegnerischen Kräften der Gesellschaft – allmählich durchzusetzen suchte. Obwohl sie eine der größten demokratischen Parteien in der ersten deutschen Republik blieb und die meisten Regierungen mittrug, geriet sie bald in die politische Defensive gegenüber deutschnationalen und rechtsradikalen Parteien, bis sie 1933 kurz nach der KPD mit allen übrigen Parteien außer der NSDAP vom neuen Regime des Nationalsozialismus verboten, ihre Führungskräfte verfolgt und ihre Strukturen zerschlagen wurden.
Seite 20

Nach dem Ende der NS-Diktatur konnte die SPD sich regenerieren und griff nun auf sozialistische Ziele zurück, die das Wiedererstarken des Faschismus durch energische Eingriffe in den Monopolkapitalismus verhindern sollten. Doch erst nach ihrer Wende zur Marktwirtschaft im Godesberger Programm 1959 wandelte sie sich zur Volkspartei. Dabei definierte sie „Sozialismus“ nun in ausdrücklicher Abgrenzung vom Sowjetkommunismus als „Demokratischen Sozialismus“, um damit ihre Anerkennung des pluralistischen Systems der westlichen Demokratien zu zeigen. So befreite die SPD sich allmählich aus ihrer Oppositionsrolle und stellte mit Willy Brandt 1969 erstmals den Bundeskanzler der Bundesrepublik Deutschland. Dessen Regierungserklärung versprach „mehr Demokratie“, jedoch keinen Sozialismus im Sinne der alten SPD-Programme mehr.

In der Sowjetischen Besatzungszone war es unter sowjetischem Einfluss zur Zwangsvereinigung der SPD mit der dominierenden KPD zur SED gekommen, die in der DDR von 1949 bis zu deren Niedergang 1989/1990 an der Macht blieb und sich an der KPdSU und dem politischen System der UdSSR ausrichtete. Dort wurde der Sozialismus weiterhin als Gegensatz zum westlichen Kapitalismus und Vorstufe zum Kommunismus aufgefasst.

Seit dem Scheitern des Realsozialismus leiteten sozialdemokratische Regierungen in Europa eine zunehmende Öffnung zur „Neuen Mitte“ ein. In der SPD begann dieser Prozess etwa 1999 mit dem „Schröder-Blair-Papier“, einer gemeinsamen Erklärung von SPD-Kanzler Gerhard Schröder und dem damaligen britischen Premier Tony Blair von der Labour Party, und führte über die Hartz-IV-Gesetze 2002 bis zur Debatte über die Streichung des demokratischen Sozialismus aus dem Parteiprogramm.

Globalisierungskritiker wie Attac und ehemalige SPD-Linke wie Oskar Lafontaine sehen darin eine Abkehr von sozialdemokratischen Grundwerten und eine Wende zum Neoliberalismus, der für sie eine besonders aggressive Steigerung des internationalen Kapitalismus ist.

Die SPD sieht sich jedoch nach wie vor als sozialistische Partei, ist Mitglied der Sozialistischen Internationale und bekennt sich in ihrem Hamburger Parteiprogramm (2007) ausdrücklich in der Tradition der „marxistischen Gesellschaftsanalyse“ zum Demokratischen Sozialismus.
Seite 21

Nationaler Sozialismus
→ Hauptartikel: Nationaler Sozialismus
Schon der Philosoph Johann Gottlieb Fichte rückte in seinen späteren Schriften vom liberalen Staatsmodell ab und ersetzte es durch ein sozialistisches, welches er im Zuge der antinapoleonischen Freiheitskriege mit nationalistischen Gedanken auflud. Er propagierte nun einen nationalen Sozialismus, der eine Mitte zwischen reinem Nachtwächterstaat und reinem Wohlfahrtsstaat bilden sollte. Sein nationaler Sozialismus orientierte sich dabei an einer vorkapitalistischen Wirtschaftsform. Die Wirtschaft sollte eine ständisch organisierte staatliche Planwirtschaft sein.[33]
Seite 22

Nationalsozialismus
→ Hauptartikel: Nationalsozialismus

Otto Strasser (1897–1974) vertrat einen antimarxistischen Sozialismus innerhalb der NSDAP
Das Verhältnis von Sozialismus und Nationalsozialismus ist unter Wissenschaftlern umstritten, was vor allem an den unterschiedlichen Verwendungen des Sozialismusbegriffs liegt. So wird die starke antiliberale Tendenz des Nationalsozialismus mitunter als „sozialistisch“ bezeichnet. Ein wesentlicher Teil der Propaganda des Nationalsozialismus waren wirtschafts- und sozialpolitische Versprechungen. Der Nationalsozialismus gab vor, im Kontrast zu den unerfüllt gebliebenen Versprechungen des Sozialismus und angesichts des Elends der Weltwirtschaftskrise ein „Sozialismus der Tat“ zu sein.[34] Dabei grenzte er sich scharf vom Marxismus ab, dessen Anhänger in der Zeit des Nationalsozialismus verfolgt und ermordet wurden.

Der Rechtswissenschaftler Johann Braun schreibt:

„Eine sozialistische Utopie liegt auch dem Nationalsozialismus zugrunde. Zwar zielt dieser nicht auf einen Sozialismus für alle ab, also nicht auf einen internationalen, sondern auf einen nationalen Sozialismus; aber die Logik des utopischen Rechtsdenkens herrscht auch hier.“[35]

Der SPD-Politiker Rudolf Breitscheid meinte auf dem Leipziger Parteitag 1931, dass „selbst der Nationalsozialismus gezwungen sei, sich ein sozialistisches Aushängeschild zu geben“. Dies zeige, „dass zuletzt doch der Gedanke des Sozialismus marschiere.“

Die sozialistischen Gruppierungen in der NSDAP wie etwa der sozialrevolutionäre Flügel um Otto Strasser verließen vor der Machtergreifung die Partei. Die Otto-Strasser-Gruppe schrieb 1930 unter dem Titel „Die Sozialisten verlassen die NSDAP“:

„Für uns bedeutet Sozialismus Bedarfswirtschaft der Nation unter Anteilnahme der Gesamtheit der Schaffenden an Besitz, Leitung und Gewinn der ganzen Wirtschaft dieser Nation, d. h. also unter Brechung des Besitzmonopols des heutigen kapitalistischen Systems und vor allem unter Brechung des Leitungsmonopols, das heute an den Besitztitel gebunden ist.“[36]

Für andere bezog der Nationalsozialismus einen wesentlichen Teil seiner ideologischen Wirkung aus der Zusammenführung von Nationalismus und Sozialismus.[37] Gemäß Götz Aly ist der Sozialismus im Begriff Nationalsozialismus nicht nur als Propagandaformel zu betrachten, vielmehr gehöre der Nationalsozialismus in die große egalitäre Grundtendenz des 20. Jahrhunderts.[38]

Laut Joachim Fest ist „die Diskussion über den politischen Standort des Nationalsozialismus nie gründlich geführt worden“. Stattdessen habe man „zahlreiche Versuche unternommen, jede Verwandtschaft von Hitlerbewegung und Sozialismus zu bestreiten“. Zwar habe Hitler keine Produktionsmittel verstaatlicht, aber „nicht anders als die Sozialisten aller Schattierungen die soziale Gleichschaltung vorangetrieben“.[39]

Der Historiker Henry A. Turner dagegen glaubt nicht, dass Hitler je Sozialist war. Er habe sich stets zum Privateigentum und zum liberalen Konkurrenzprinzip bekannt, aber nicht aus einem echten Liberalismus heraus, sondern auf Grund seiner sozialdarwinistischen Grundannahmen. Im Sinne eines Primats der Politik habe er postuliert, die Wirtschaft müsse stets unter der vollständigen Kontrolle der Politik stehen. Eine konsistente ökonomische Theorie habe der Nationalsozialismus nie entwickelt.[40] Der Sozialhistoriker Hans-Ulrich Wehler urteilt, dass der Sozialismus im Nationalsozialismus „allenfalls in verballhornter Form“ fortlebte, nämlich in der Ideologie der Volksgemeinschaft.[41]
Seite 23

Neue Linke

Rudi Dutschke (1940–1979) Wortführer der bundesdeutschen Neuen Linken
Aus der Außerparlamentarischen Opposition der 1960er Jahre gingen seit 1970 zum einen eine Reihe von K-Gruppen, zum anderen „undogmatische“ und „antiautoritäre“ Gruppen hervor, die als „Neue Linke“ zusammengefasst werden. Unter ihnen war das 1969 gegründete Sozialistische Büro in Offenbach eine der einflussreichsten Organisationen. Studentenführer wie Rudi Dutschke vertraten einen demokratischen Sozialismus, den sie sowohl gegen die Sozialdemokratie als auch gegen den Realsozialismus abgrenzten. Sie blieben meist außerhalb von Parteien in verschiedenen Neuen sozialen Bewegungen engagiert und hatten kaum Rückhalt in der Arbeiterschaft und bei Gewerkschaften, gewannen aber mit Gründung und Aufstieg der neuen Partei Die Grünen parlamentarischen Einfluss. Kulturell erreichte die Deutsche Studentenbewegung der 1960er Jahre eine Liberalisierung der Gesellschaft und differenziertere Haltung zum Ideal des Sozialismus als im Kalten Krieg, wo dieser Begriff fast nur mit diktatorischen Zuständen östlicher Systeme identifiziert wurde.

Neue sozialistische Parteien
Demokratischer Sozialismus, zwischen 1928 und 1934 aus kommunistischer Sicht im Zusammenhang mit der SPD noch als Sozialfaschismus verschrien, wurde auch in der DDR von der kommunistischen SED meist als ein Synonym für Sozialdemokratie definiert und als „Sozialdemokratismus“[42] ideologisch abgewertet. Nach der Wende in der DDR erklärte die gestürzte SED diesen Begriff aber zu ihrer Leitidee, indem sie sich 1990 zur Partei des Demokratischen Sozialismus (PDS) umbenannte und sich programmatisch wandelte. 2005 benannte sich die PDS in Die Linkspartei um und vereinte sich am 16. Juni 2007 mit der westdeutschen WASG zur neugebildeten Partei Die Linke.

In anderen Staaten Westeuropas hatten kommunistische Parteien schon seit den 1960er Jahren einen antisowjetkommunistischen Kurs zum Eurokommunismus eingeschlagen: etwa die Kommunistische Partei Italiens, die sich 1990 umbenannte in „Demokratische Partei der Linken“ (italienisch Partito Democratico della Sinistra – PDS) oder die Kommunistische Partei Frankreichs (KPF, französisch PCF). Diese ehemals kommunistischen Parteien setzen zum einen auf einen Ausbau des Sozialstaats und eine Zähmung des Kapitalismus durch gesetzliche Eingriffe, zum anderen wollen sie den Parlamentarismus stärker mit Plebisziten und direkter Demokratie ergänzen.

Im Vorfeld der Wahlen zum russischen Staatspräsidenten hat auch der letzte Präsident der früheren UdSSR, Michail Gorbatschow, im Oktober 2007 eine sozialdemokratische Bewegung gegründet, um Tendenzen zu einer neuen Diktatur, Abbau von sozialen Rechten und Massenverarmung in Russland zu begegnen.[43]
Seite 24

Perspektiven

José Mujica (* 1935) war 2010–2015 Präsident Uruguays und vertrat sozialistische Positionen
Eine wissenschaftliche Debatte über Sozialismus als alternativen Gesellschaftsentwurf, wie es sie während der deutschen Studentenbewegung der 1960er Jahre an den Universitäten gab, findet heute kaum mehr statt. Nur einzelne Sozialwissenschaftler wie Wolfgang Fritz Haug fordern angesichts eines Turbokapitalismus heutzutage und der damit verbundenen Lebensweisen, aus den historischen Erfahrungen zu lernen und das sozialistische Projekt zu aktualisieren. Eine kritische Bestandsaufnahme unternimmt unter anderem die Zeitschrift Das Argument und die dort ebenfalls angesiedelte Edition des Historisch-kritischen Wörterbuchs des Marxismus (HKWM). Auch im Umfeld der zur Partei Die Linke gehörenden Rosa-Luxemburg-Stiftung wird eine zukünftige alternative Lebensweise mit Sozialismus diskutiert.

Der Sozialphilosoph Axel Honneth hat mit seiner Schrift Die Idee des Sozialismus eine Kritik der ursprünglichen Idee des in der Industriellen Revolution wurzelnden Sozialismus vorgelegt und als dessen Kerngedanken die „soziale Freiheit“ neu definiert. Sozialismus bedeute heute experimentelle politische Ankersetzung auf dem Weg zu einer solidarischen Gesellschaft, die nicht nur auf der wirtschaftlichen, sondern auch in der politischen Ebene und in den persönlichen Beziehungen (insbesondere zwischen den Geschlechtern) anzustreben sei.[44]

Ebenfalls eine Neuinterpretation stellt der politische Soziologe Heinz Dieterich mit seinem Konzept vom Sozialismus des 21. Jahrhunderts dar, in dem er versucht, marxistische Werttheorie mit basisdemokratischen Elementen zu verknüpfen, der dann eine nicht-marktwirtschaftliche, demokratisch von den unmittelbar Wertschaffenden bestimmende Äquivalenzökonomie zu Grunde liegt. Versuche, diese neue Theorie in die Praxis umzusetzen, finden sich derzeit in Venezuela (Bolivarismus) und Bolivien. Die Theorie eines Demokratischen Konföderalismus wird gegenwärtig in verschiedenen kurdischen Organisationen und Lokalverwaltungen sozialistischer Prägung zu realisieren versucht (Rojava, YPG).

Wolfram Elsner, Professor für Volkswirtschaftslehre an der Universität Bremen, sieht im Sozialismus chinesischer Prägung „gegenüber dem alten, eurozentrierten Sozialismusentwurf“, aber auch gegenüber dem „neoliberalen Finanzmarktkapitalismus“ ein „effektiveres Modell“. In seinem 2020 erschienenen Buch Das chinesische Jahrhundert schreibt er: „China ist heute fähig, die jahrzehntelange Diskreditierung und Tabuisierung jeder Idee von realem Sozialismus wieder aufzubrechen, vor allem weil es zeigt, dass Sozialismus im 21. Jahrhundert kein statisches, bürokratisches Armutssystem mehr ist, sondern diesbezüglich den real existierenden Kapitalismus sogar überflügeln und die menschlichen Perspektiven erweitern kann.“[45]
Seite 25

Kritik
→ Hauptartikel: Sozialismuskritik
Der Sozialismus war stets Kritik seitens seiner ideologischen Gegner ausgesetzt. Andererseits gab es aus den zahlreichen einzelnen sozialistischen Strömungen Kritik an Nebenströmungen und den bestehenden sozialistischen Verhältnissen.

Konservatismus
Fjodor Michailowitsch Dostojewski, der in seiner Jugend selber Sozialist gewesen war, verurteilte später die Idee des Sozialismus. Einerseits machte er die Bedeutung der Kunst als Anästhetikum geltend und erkannte in provokanten Formeln wie „ein Paar Stiefel sei wichtiger als Shakespeare und eine Eierverkauferin nötiger als Puschkin“ des Nihilisten Dmitri Iwanowitsch Pissarew den Versuch, die Kunst durch das allgemeine Glück überflüssig werden zu lassen. Die persönliche Freiheit schätzte er besonders hoch, weshalb er seit Verbrechen und Strafe (1866) gegen die aufkommende Milieutheorie der gerade entstehenden Soziologie polemisierte. Gleichzeitig erkannte er im Atheismus der russischen Frühsozialisten den Kern ihrer Vorstellung von Perfektibilität und in der daran anschließenden Forderung nach einer Revolution mit der Errichtung einer utopischen Ordnung das Ende der Freiheit, wofür er in seinem Roman Die Dämonen (1873) das Bild vom Kristallpalast aus Nikolai Gawrilowitsch Tschernyschewskis Roman Was tun? aufgriff und nicht als Ausdruck menschlicher Schöpferkraft und Selbstbefreiung durch Technik wertete, sondern als Fortschrittsglauben, Materialismus, Ausdruck von Sterilität und Durchrationalisierung der Massen, womit er seinen Einspruch für die Fehlbarkeit des Menschens geltend machte. Gemeinsam mit dem Konservativen Konstantin Petrowitsch Pobedonoszew entwickelte er in der Zeitschrift Der Staatsbürger eine antiliberale wie antisozialistische Vorstellung von der russischen Orthodoxie und dem Zarenreich als Träger heilsgeschichtlicher Sendung. Die Begegnung mit Wladimir Sergejewitsch Solowjow führte ihn zu einer ethischen Kritik am Sozialismus, wonach er seine Ablehnung zwar beibehielt, jedoch andere Akzente setze.[46]

Stark beeinflusst durch Dostojewskis Werke war der deutsche Philosoph Friedrich Nietzsche. Er wies darauf hin, dass der Sozialismus der jüngere Bruder des fast abgelebten Despotismus sei, den er beerben wolle. Er brauche eine Fülle an Staatsgewalt und strebe die Vernichtung des Individuums an. Der cäsarische Gewaltstaat, den die Sozialisten seiner Meinung nach anstrebten, brauche die Niederwerfung aller Bürger und könne sich nur durch äußersten Terrorismus Hoffnung auf Existenz machen. Er bereite sich im Stillen auf eine Schreckensherrschaft vor und verwende missbräuchlich den Begriff der Gerechtigkeit. Der Sozialismus lehre die Gefahr der Anhäufung von Staatsgewalt und werde den Ruf nach so wenig Staat wie möglich provozieren.[47]
Seite 26

Liberalismus
Seit dem Beginn der Auseinandersetzung in Frankreich zwischen der politischen Ökonomie und dem Sozialismus wurde den sozialistischen Kritikern der Marktwirtschaft vorgeworfen, dass sie über keine praxistauglichen Alternativen verfügten, bzw. dass verschiedene bereits gemachte Experimente schmählich gescheitert seien. Unter den neueren Ökonomen warf Eugen von Böhm-Bawerk, ein Vertreter der Österreichischen Schule, in Kapital und Kapitalzins (1884–1902) dem Marxismus gegenüber erstmals das Problem der Wirtschaftsrechnung im Sozialismus auf, ein Argument, das von Ludwig von Mises in der Folge ausgebaut wurde. Der Sozialismus negiere den gesamten Marktprozess und damit würden Marktpreise als Signale für Knappheit fehlen. Dadurch gebe keinerlei Möglichkeit, Investitionsalternativen rational zu bewerten, wie Mises aus seiner Handlungstheorie deduktiv herleitete. Allerdings komme es in einer gemischten Wirtschaftsform mit Privateigentum an Produktionsmitteln und staatlicher Interventionen letztlich zum gleichen Problem, nur moderater, da in dem Ausmaß, wie der Staat in den Markt eingreife, auch hier die Bildung von sinnvollen Preisen durchkreuzt und damit die Richtung der Produktion verändert würden. Der Regierung bleibe nur, entweder zu einem freien Markt zurückzukehren oder aber zu versuchen, durch weitere Interventionen, die ihrerseits wieder die wettbewerbliche Struktur der Marktpreise stören würden, die Schieflage zu korrigieren. Die Wirtschaft jedes interventionistischen Staates sei daher unvermeidlich instabil.[48]

Milton Friedman betont, sozialistisch gesteuerte Volkswirtschaften würden generell qualitativ schlechtere Produkte zu höheren Preisen produzieren.[49]

Nach Ansicht Friedrich August von Hayeks kollidiert die Vergesellschaftung der Produktionsmittel zwangsläufig mit den Individualrechten und der Rechtsstaatlichkeit. Die Wahrung der Rechtsstaatlichkeit würde eine Selbstbeschränkung der Planungsbehörden erfordern, zu der diese nicht in der Lage seien, da sie sonst ihren Aufgaben nicht nachkommen könnten.[50]

Laut dem Ökonomen Jürgen Pätzold verlange zentrale Planung „in gesellschaftspolitischer Hinsicht den Kollektivismus und in staatspolitischer Hinsicht den Totalitarismus des Einparteiensystems“. Demgegenüber setze eine funktionierende Marktwirtschaft voraus, dass sie in ein System politischer und ökonomischer Freiheiten eingebettet sei. Ein solches System der Freiheiten sei mit einer Zentralverwaltungswirtschaft unvereinbar, da darin die Handlungs- und Bewegungsfreiheit der Individuen einen latenten Störfaktor bilde, der versuche, den Staat zurückzudrängen.[51]
Seite 27

Immanente Kritik
Trotzkistische Kritik
→ Hauptartikel: Verratene Revolution. Was ist die Sowjetunion und wohin treibt sie?
Während Trotzki die Sowjetunion noch als einen – zwar „bürokratisch degenerierten“ – Arbeiterstaat ansah, verbreitete Tony Cliff und die von seinen Ideen beeinflusste International Socialist Tendency die Version eines staatskapitalistischen Systems mit allen Merkmalen kapitalistischer Klassenherrschaft.

Budapester Schule
Die Budapester Schule um Ágnes Heller und Ferenc Fehér analysierte mit marxistischem Instrumentarium die Sowjetgesellschaften als totalitäre Systeme mit einer „Diktatur über die Bedürfnisse“.

Kritik des real existierenden Sozialismus
Eine marxistisch fundierte Analyse und Kritik des „real existierenden Sozialismus“ als einer „nichtkapitalistischen“ Klassengesellschaft unter der Diktatur von Partei und Bürokratie legte Rudolf Bahro 1977 mit seiner bekannten Publikation Die Alternative vor.

2018 versuchte der Sozialwissenschaftler Ulrich Knappe 2018, das ökonomische Wesen des vergangenen „paradoxen“, gemeint war: real existierenden Sozialismus mit Hilfe der Marxschen Gesellschaftsanalyse am Beispiel von Russland (Sowjetunion) und China zu entziffern.[52]

Postmoderne
Der poststrukturalistische Soziologe und Philosoph Jean Baudrillard kritisiert in Die göttliche Linke – Chronik der Jahre 1977–1984 mit Blick auf die französischen Verhältnisse die aus seiner Sicht nicht mehr zeitgemäßen Ziele des Sozialismus. Während der Sozialismus noch immer von einer transparenten und kohärenten Gesellschaft träume, hätten die Menschen ein solches Bedürfnis nach Anschluss, Kontakt und Kommunikation kaum noch. Nach dem Philosophen Wolfgang Welsch könne ein Baudrillard diese Sozialismus-Kritik schwerlich äußern. Baudrillards Kritik sei dabei bloß narzisstisch und ein Vehikel, um seine eigene antiquierte Diagnose als aktuell erscheinen zu lassen.[53]
Seite 28"""
print(json.dumps(create_json_object(extract_sections(longtext))))
#test_detect_page_number()
# adapt_weights()
#adapt_weights_gradient()

def test_extract_sections():
    # Test case 1: Normal case with a mix of headlines and text
    text1 = """HEADLINE1
Text1 Text 2 Text 3 Text 4.
HEADLINE2
Txt2.
HEADL3
Txt3.
HEADL4
Txt4.
HEADL5
Text1 Text 2 Text 3 Text 4. Text 5.
HEADL6
Txt6."""

    expected_output1 = {
        0: ('HEADLINE1', 'Text1 Text 2 Text 3 Text 4.'),
        1: ('HEADLINE2', 'Txt2.\nHEADL3\nTxt3.'),
        2: ('HEADL4', 'Txt4.'),
        3: ('HEADL5', 'Text1 Text 2 Text 3 Text 4. Te'),
        4: ('Continuing previous section', 'xt 5.'),
        5: ('HEADL6', 'Txt6.')
    }

    # Test case 2: Only headlines
    text2 = """HEADLINE1
HEADLINE2
HEADL3
HEADL4
HEADL5
HEADL6"""

    expected_output2 = {
        0: ('HEADLINE1', 'HEADLINE2\nHEADL3'),
        1: ('HEADL4', 'HEADL5\nHEADL6')
    }

    # Test case 3: Only text
    text3 = """Text1 Text 2 Text 3 Text 4.
Txt2.
Txt3.
Txt4.
Text1 Text 2 Text 3 Text 4. Text 5.
Txt6."""

    expected_output3 = {
        0: ('NO_HEADLINES_FOUND', 'Text1 Text 2 Text 3 Text 4.\nTx'),
        1: ('NO_HEADLINES_FOUND', 't2.\nTxt3.\nTxt4.\nText1 Text 2 T'),
        2: ('NO_HEADLINES_FOUND', 'ext 3 Text 4. Text 5.\nTxt6.')
    }

    # Test case 4: Empty text
    text4 = ""

    expected_output4 = {}

    # Test case 5: Longer text with varying lengths
    text5 = """HEADLINE1
Text1 Text 2 Text 3 Text 4. Text 5. Text 6. Text 7. Text 8.
HEADLINE2
Text1 Text 2 Text 3 Text 4.
HEADL3
Txt3.
HEADL4
Txt4.
HEADL5
Text1 Text 2 Text 3 Text 4. Text 5. Text 6.
HEADL6
Txt6."""

    expected_output5 = {
        0: ('HEADLINE1', 'Text1 Text 2 Text 3 Text 4. Te'),
        1: ('Continuing previous section', 'xt 5. Text 6. Text 7. Text 8.'),
        2: ('HEADLINE2', 'Text1 Text 2 Text 3 Text 4.'),
        3: ('HEADL3', 'Txt3.\nHEADL4\nTxt4.'),
        4: ('HEADL5', 'Text1 Text 2 Text 3 Text 4. Te'),
        5: ('Continuing previous section', 'xt 5. Text 6.'),
        6: ('HEADL6', 'Txt6.')
    }

    # Test case 6: Single headline followed by a long text
    text6 = """HEADLINE1
Text1 Text 2 Text 3 Text 4. Text 5. Text 6. Text 7. Text 8. Text 9. Text 10. Text 11. Text 12. Text 13. Text 14. Text 15. Text 16."""

    expected_output6 = {
        0: ('HEADLINE1', 'Text1 Text 2 Text 3 Text 4. Te'),
        1: ('Continuing previous section', 'xt 5. Text 6. Text 7. Text 8.'),
        2: ('Continuing previous section', 'Text 9. Text 10. Text 11. Text'),
        3: ('Continuing previous section', '12. Text 13. Text 14. Text 15'),
        4: ('Continuing previous section', '. Text 16.')
    }


    # Test case 7: Long headline that exceeds the MAX_VECTOR_LENGTH limit
    text7 = """HEADLINE1234567890123456789012345678901
    Text1 Text 2 Text 3 Text 4."""

    expected_output7 = {
        0: ('HEADLINE1234567890123456789012345678901', 'Text1 Text 2 Text 3 Text 4.')
    }

    # Test case 8: Headline with a colon
    text8 = """HEADLINE1:
Text1 Text 2 Text 3 Text 4. Text 5. Text 6. Text 7. Text 8. Text 9. Text 10. Text 11. Text 12. Text 13. Text 14. Text 15. Text 16."""

    expected_output8 = {
        0: ('NO_HEADLINES_FOUND', 'HEADLINE1:\nText1 Text 2 Text 3'),
        1: ('NO_HEADLINES_FOUND', 'Text 4. Text 5. Text 6. Text'),
        2: ('NO_HEADLINES_FOUND', '7. Text 8. Text 9. Text 10. Te'),
        3: ('NO_HEADLINES_FOUND', 'xt 11. Text 12. Text 13. Text'),
        4: ('NO_HEADLINES_FOUND', '14. Text 15. Text 16.')
    }

    # Test case 9: Multiple headlines followed by a single long text
    text9 = """HEADLINE1
HEADLINE2
HEADL3
HEADL4
Text1 Text 2 Text 3 Text 4. Text 5. Text 6. Text 7. Text 8. Text 9. Text 10. Text 11. Text 12. Text 13. Text 14. Text 15. Text 16."""

    expected_output9 = {
        0: ('HEADLINE1', 'HEADLINE2\nHEADL3'),
        1: ('HEADL4', 'Text1 Text 2 Text 3 Text 4. Te'),
        2: ('Continuing previous section', 'xt 5. Text 6. Text 7. Text 8.'),
        3: ('Continuing previous section', 'Text 9. Text 10. Text 11. Text'),
        4: ('Continuing previous section', '12. Text 13. Text 14. Text 15'),
        5: ('Continuing previous section', '. Text 16.')
    }

    # Run the tests and check if the output
    print("Running tests...")
    run_tests(1, "Normal case with a mix of headlines and text", text1, expected_output1)
    run_tests(2, "Only headlines", text2, expected_output2)
    run_tests(3, "Only text", text3, expected_output3)
    run_tests(4, "Empty text", text4, expected_output4)
    run_tests(5, "Longer text with varying lengths", text5, expected_output5)
    run_tests(6, "Single headline followed by a long text", text6, expected_output6)
    run_tests(7, "Long headline that exceeds the MAX_VECTOR_LENGTH limit", text7, expected_output7)
    run_tests(8, "Headline with a colon", text8, expected_output8)
    run_tests(9, "Multiple headlines followed by a single long text", text9, expected_output9)

    print("Tests finished!")

def run_tests(id, description, text, expected_output):
    print(f"Test case {id}: {description}")
    try:
        assert extract_sections(text) == expected_output
    except AssertionError:
        print(f"Test case {id} failed!")
        print("Expected output:")
        print(expected_output)
        print("Actual output:")
        print(extract_sections(text))
    else:
        print(f"Test case {id} passed!")

def test_headlines():
    print("Testing headlines regex...")
    run_tests(1, "Test headlines 1", "HEADLINESTART\ntext1\nDies ist einXXX Test\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('Dies ist einXXX Test', 'text2')})
    run_tests(2, "Test headlines 2", "HEADLINESTART\ntext1\nA) Es ist nichtXXX wahr\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('A) Es ist nichtXXX wahr', 'text2')})
    run_tests(3, "Test headlines 3", "HEADLINESTART\ntext1\n1. XXXTest\ntext2", {0: ('HEADLINESTART', 'text1\n1. XXXTest\ntext2')})
    run_tests(4, "Test headlines 4", "HEADLINESTART\ntext1\nii. XXXTest2\ntext2", {0: ('HEADLINESTART', 'text1\nii. XXXTest2\ntext2')})
    run_tests(5, "Test headlines 5", "HEADLINESTART\ntext1\nB) Es ist XXXdoch wahr\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('B) Es ist XXXdoch wahr', 'text2')})
    run_tests(6, "Test headlines 6", "HEADLINESTART\ntext1\ni. Die NeudeutscheXXX Frage\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('i. Die NeudeutscheXXX Frage', 'text2')})
    run_tests(7, "Test headlines 7", "HEADLINESTART\ntext1\na. Meine MeinungXXX dazu\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('a. Meine MeinungXXX dazu', 'text2')})
    run_tests(8, "Test headlines 8", "HEADLINESTART\ntext1\nb. Die Meinung XXXmeiner Frau dazu\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('b. Die Meinung XXXmeiner Frau dazu', 'text2')})
    run_tests(9, "Test headlines 9", "HEADLINESTART\ntext1\niv. AbschnittXXX C\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('iv. AbschnittXXX C', 'text2')})
    run_tests(10, "Test headlines 10", "HEADLINESTART\ntext1\nv. AbschnittXXX F\ntext2", {0: ('HEADLINESTART', 'text1'), 1: ('v. AbschnittXXX F', 'text2')})
    run_tests(11, "Test headlines 11", "HEADLINESTART\ntext1\nWenn man es allerdings doch weiß, dann funktioniert das gut!\ntext2", {0: ('HEADLINESTART', 'text1\nWenn man es allerdings d'), 1:('Continuing previous section','och weiß, dann funktioniert da'), 2:('Continuing previous section','s gut!\ntext2')})
 
    run_tests(12, "Test headlines 12", "HEADLINESTART\ntext1\nWenn das nicht wahr ist, dann hat man ein Problem.\ntext2", {0: ('HEADLINESTART', 'text1\nWenn das nicht wahr ist,'), 1:('Continuing previous section','dann hat man ein Problem.\ntex'), 2:('Continuing previous section','t2')})
    run_tests(13, "Test headlines 13", "HEADLINESTART\ntext1\n\"Nein das will ich nicht.\"\ntext2", {0: ('HEADLINESTART', 'text1\n\"Nein das will ich nicht'),1: ('Continuing previous section', '.\"\ntext2')})
    run_tests(14, "Test headlines 14", "HEADLINESTART\ntext1\n„Nein, das will ich nicht.“\ntext2", {0: ('HEADLINESTART', 'text1\n„Nein, das will ich nich'),1: ('Continuing previous section', 't.“\ntext2')})
    run_tests(15, "Test headlines 15", "HEADLINESTART\ntext1\nDies ist eine Quellenangabe.[20]\ntext2", {0: ('HEADLINESTART', 'text1\nDies ist eine Quellenang'),1: ('Continuing previous section', 'abe.[20]\ntext2')})

#test_extract_sections()
#test_headlines()