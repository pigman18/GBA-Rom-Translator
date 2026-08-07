const texts = require('./texts.json');
const texts_translated = require('./texts_translated.json');

/**
 * 反查原文地址
 * @param original
 * @return {string}
 */
function getAddressList(original) {
    return (texts.entries || []).filter((e) => (e['original'] || '') === original)
        .map((e) => e.address);
}

// 查出明显异常的译文
let addressList = [];
for(let tt of texts_translated) {
    if ((tt.translated || '').indexOf('Ö') !== -1) {
        // 根据原本反查地址
        addressList.push(...getAddressList(tt.original));
    }
}
console.log(`--addrs "${[...new Set(addressList)].join(',')}"`);
