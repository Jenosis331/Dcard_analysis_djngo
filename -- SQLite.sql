-- SQLite
DELETE FROM dcard_data1_all
WHERE category = 'D';
DELETE FROM dcard_data2_preprocessed_all
WHERE category = 'D';
DELETE FROM dcard_data3_tokenpos_all
WHERE category = 'D';
DELETE FROM dcard_top_person
WHERE category = 'D';