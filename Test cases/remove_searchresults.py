import json
import re

def remove_searchresults(searchresults, keep_json, moresearches):
    # Returns a version of searchresults with every entry removed that is NOT listed in keep_json.
    # Keep only entries that are listed in keep_json.
    # If there is no 'cleanup' object in keep_json, or on error, return False.
    # Update indices in moresearches to reflect the changes in searchresults.
    # Adds links to moresearches, if an index is removed.
    if keep_json is None:
        print("remove_searchresults - invalid keep_json")
        return False, moresearches
    try:
        if "cleanedup" in keep_json:
            cleanedup_indices = set(map(int, keep_json["cleanedup"]))
            cleaned_searchresults = [searchresults[i] for i in range(len(searchresults)) if i in cleanedup_indices]

            reindexed_searchresults = []
            index_map = {}
            for new_idx, old_idx in enumerate(cleanedup_indices):
                if old_idx < len(searchresults):  # Check if old_idx is within range of searchresults
                    old_key = str(old_idx)
                    result = {key: value for key, value in searchresults[old_idx].items() if key == old_key}
                    reindexed_searchresults.append({str(new_idx): result[old_key]})
                    index_map[old_idx] = new_idx

            # Update the 'documents' list and 'links' list in moresearches
            if "documents" in moresearches:
                updated_documents = []
                for doc_idx in moresearches["documents"]:
                    int_doc_idx = int(doc_idx)
                    if int_doc_idx in index_map:
                        updated_documents.append(str(index_map[int_doc_idx]))
                    else:
                        if int_doc_idx < len(searchresults):  # Check if int_doc_idx is within range of searchresults
                            if "links" not in moresearches:
                                moresearches["links"] = []
                            moresearches["links"].append(searchresults[int_doc_idx][doc_idx]["URL"])
                            if "openLinks" not in moresearches["action"]:
                                moresearches["action"].append("openLinks")
                moresearches["documents"] = updated_documents
            return reindexed_searchresults, moresearches
        else:
            print("remove_searchresults - no \"cleanedup\" object detected")
            return False, moresearches
    except Exception as e:
        print(f"Error in remove_searchresults: {e}")
        print(f"searchresults: {searchresults}, keep_json: {keep_json}, moresearches: {moresearches}")
        return False, moresearches

def extract_json_object(text):
    # Extracts the first JSON object from the given text
    try:
        json_str = re.search(r'\{.*\}', text).group()
        return json.loads(json_str)
    except (AttributeError, json.JSONDecodeError):
        return None

def test_remove_searchresults():
    # Test the remove_searchresults function
    # Test case 1
    print("Test case 1")
    searchresults = [{"0": {"URL": "https://www.0.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.1.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"2": {"URL": "https://www.2.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"3": {"URL": "https://www.3.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    keep_json = '{"cleanedup": ["1", "3"]}'
    moresearches = {"action": ["viewDocuments"], "documents": ["0"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == [{"0": {"URL": "https://www.1.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.3.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    assert moresearches == {"action": ["viewDocuments", "openLinks"], "documents": [], "links": ["https://www.0.com/"]}
    print("Test case 1 passed")

    # Test case 2
    print("Test case 2")
    keep_json = '{"cleanedup": ["1", "3"]}'
    moresearches = {"action": ["viewDocuments"], "documents": ["0", "1"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == [{"0": {"URL": "https://www.1.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.3.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    assert moresearches == {"action": ["viewDocuments", "openLinks"], "documents": ["0"], "links": ["https://www.0.com/"]}
    print("Test case 2 passed")

    # Test case 3
    print("Test case 3")
    keep_json = '{"cleanedup": ["0"]}'
    moresearches = {"action": ["viewDocuments"], "documents": ["0", "1"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == [{"0": {"URL": "https://www.0.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    assert moresearches == {"action": ["viewDocuments", "openLinks"], "documents": ["0"], "links": ["https://www.1.com/"]}
    print("Test case 3 passed")

    # Test case 4
    print("Test case 4")
    # Test case with empty cleanedup list
    keep_json = '{"cleanedup": []}'
    moresearches = {"action": ["viewDocuments"], "documents": ["0", "1", "2", "3"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == []
    assert moresearches == {"action": ["viewDocuments", "openLinks"], "documents": [], "links": ["https://www.0.com/", "https://www.1.com/", "https://www.2.com/", "https://www.3.com/"]}
    print("Test case 4 passed")

    # Test case 5
    print("Test case 5")
    # Test case that should return a moresearches object without 'documents' and 'links' entries, because document '4' is not in the search results
    keep_json = '{"cleanedup": ["4", "5"]}'
    moresearches = {"action": ["viewDocuments"], "documents": ["4"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == []
    assert moresearches == {"action": ["viewDocuments"], "documents": []}
    print("Test case 5 passed")

    # Test case 6
    print("Test case 6")
    # Test case with empty search results
    searchresults = []
    keep_json = '{"cleanedup": ["0", "1", "2", "3"]}'
    moresearches = {"action": ["viewDocuments"], "documents": ["0", "1", "2", "3"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == []
    assert moresearches == {"action": ["viewDocuments"], "documents": []}
    print("Test case 6 passed")

    # Test case 7
    print("Test case 7")
    # Test case with an invalid JSON format in keep_json
    searchresults = [{"0": {"URL": "https://www.0.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.1.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"2": {"URL": "https://www.2.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"3": {"URL": "https://www.3.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    keep_json = '{INVALID_JSON}'
    moresearches = {"action": ["viewDocuments"], "documents": ["0"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == False
    print("Test case 7 passed")

    # Test case 8
    print("Test case 8")
    # Test case with empty searchresults and keep_json
    searchresults = []
    keep_json = '{}'
    moresearches = {"action": ["viewDocuments"], "documents": ["0"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == False
    print("Test case 8 passed")

    # Test case 9
    print("Test case 9")
    # Test case with empty moresearches
    searchresults = [{"0": {"URL": "https://www.0.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.1.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"2": {"URL": "https://www.2.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"3": {"URL": "https://www.3.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    keep_json = '{"cleanedup": ["0", "2"]}'
    moresearches = {}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == [{"0": {"URL": "https://www.0.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.2.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    assert moresearches == {}
    print("Test case 9 passed")

    # Test case 10
    print("Test case 10")
    # Test case with missing 'action' key in moresearches
    keep_json = '{"cleanedup": ["0", "2"]}'
    moresearches = {"documents": ["0"]}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, extract_json_object(keep_json), moresearches)
    assert reindexed_searchresults == [{"0": {"URL": "https://www.0.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.2.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    assert moresearches == {"documents": ["0"]}
    print("Test case 10 passed")

    # Test case 11
    print("Test case 11")
    # Test case with searchresults with multiple entries with the same key
    searchresults = [
        {'0': {"URL": "https://www.0.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},
        {'1': {"URL": "https://www.1.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},
        {'1': {"URL": "https://www.1a.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},
        {'1': {"URL": "https://www.1b.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},
        {'4': {"URL": "https://www.4.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},
        {'5': {"URL": "https://www.5.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},
        {'6': {"URL": "https://www.6.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},
        {'7': {"URL": "https://www.7.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}
    ]
    keep_json = {'cleanedup': ['1', '4', '5']}
    moresearches = {"action": ["search"], "keywords": ["Martin Fürholz"], "documents": [], "links": []}
    reindexed_searchresults, moresearches = remove_searchresults(searchresults, keep_json, moresearches)
    assert reindexed_searchresults == [{"0": {"URL": "https://www.1.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"1": {"URL": "https://www.4.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}},{"2": {"URL": "https://www.5.com/", "summary": "Test", "prozent": "unknown", "keyword": "Test"}}]
    assert moresearches == {"action": ["search"], "keywords": ["Martin Fürholz"], "documents": [], "links": []}
    print("Test case 11 passed")

test_remove_searchresults()