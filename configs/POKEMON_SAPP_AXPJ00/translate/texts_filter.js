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

function isError4(original, translated) {
    return translated.indexOf('Ｅ') !== -1
        || translated.indexOf('E') !== -1
        || translated.indexOf('►') !== -1
        || translated.indexOf('埃伊：') !== -1
        || translated.indexOf('呃哦') !== -1
}


// 移除无效的译文
let tt2 = texts_translated.filter((tt) => {
    let originalLength = (tt.original || '').length;
    let translatedLength = (tt.translated || '').length;
    if (translatedLength >= originalLength * 3) {
        return false;
    }
    let al = getAddressList(tt.original);
    return al.length > 0 && ((tt.translated || '').indexOf('|||') === -1) && tt.status !== 404;
});
texts_translated = tt2;
fs.writeFileSync('./texts_translated.json', JSON.stringify(texts_translated, null, 2));

// 查出明显异常的译文
// let addressList = [];
// for(let tt of texts_translated) {
//     let original = (tt.original || '');
//     let translated = (tt.translated || '');
//     let isError = isError1(translated) ||
//         isError2(translated) ||
//         isError3(translated) ||
//         isError4(original, translated);
//     if (isError) {
//         // 根据原本反查地址
//         let al = getAddressList(tt.original);
//         if (al.length > 0) {
//             console.log(`异常内容：${tt.translated}`);
//             addressList.push(...al);
//         }
//     }
// }
// console.log(`--addrs "${[...new Set(addressList)].join(',')}"`);


