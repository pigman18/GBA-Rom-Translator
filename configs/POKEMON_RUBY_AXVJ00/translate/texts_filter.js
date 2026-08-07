const fs = require('node:fs');
let texts = require('./texts.json');
let texts_translated = require('./texts_translated.json');

/**
 * 反查原文地址
 * @param original
 * @return {string}
 */
function getAddressList(original) {
    return (texts.entries || []).filter((e) => (e['original'] || '') === original)
        .map((e) => e.address);
}

function isError1(translated) {
    return translated.indexOf('Ö') !== -1;
}

function isError2(translated) {
    return translated.indexOf('ｏ') !== -1;
}

function isError3(translated) {
    return translated.split(' ').length > 6;
}

// 移除无效的译文
let tt2 = texts_translated.filter((tt) => {
    let al = getAddressList(tt.original);
    return al.length > 0;
});
texts_translated = tt2;
fs.writeFileSync('./texts_translated.json', JSON.stringify(texts_translated, null, 2));

// 查出明显异常的译文
let addressList = [];
for(let tt of texts_translated) {
    let translated = (tt.translated || '');
    let isError = isError1(translated) ||
        isError2(translated) ||
        isError3(translated);
    if (isError) {
        // 根据原本反查地址
        let al = getAddressList(tt.original);
        if (al.length > 0) {
            console.log(`异常内容：${tt.translated}`);
            addressList.push(...al);
        }
    }
}
console.log(`--addrs "${[...new Set(addressList)].join(',')}"`);


