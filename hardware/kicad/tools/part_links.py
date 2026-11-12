"""Datasheet and product links written into every schematic symbol.

The part number comes from the BOM tables (gen_bom.resolve), so the links
follow whatever part is actually ordered. Datasheet links below were checked
to resolve to the maker's PDF; parts whose maker blocks scripted checks link
their Digi-Key product page instead (it carries the datasheet).
"""

from urllib.parse import quote

import gen_bom

# MPN prefix -> datasheet URL (longest prefix wins)
DATASHEETS = {
    '1571300': 'https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv'
    '&DocNm=1571300&DocType=Customer+Drawing&DocLang=English',
    'EVQ-P2F02K': 'https://www.mouser.com/en/ProductDetail/Panasonic-Industry/EVQ-P2F02K',
    'EVP-AA': 'https://industry.panasonic.com/ap/en/products/control/switch/light-touch/number/evpaa802q',
    'APGB0607': 'https://www.kingbrightusa.com/images/catalog/SPEC/APGB0607G22R23C.pdf',
    'ESP32-S3-WROOM-2':'https://www.espressif.com/sites/default/files/'
    'documentation/esp32-s3-wroom-2_datasheet_en.pdf',
    'OPA1655': 'https://www.ti.com/lit/ds/symlink/opa1656.pdf',
    '54-00164': 'https://www.digikey.com/en/products/detail/tensility/54-00164/10459298',
    'MJ-3523': 'https://www.sameskydevices.com/product/resource/mj-3523-smt.pdf',
    '61900311021': 'https://www.we-online.com/components/products/datasheet/61900311021.pdf',
    'SWR25X': 'https://static.datasheets.com/doc/20841721-sullins-swr25x-nrtc-s20-st-ba-ds.pdf',
    'OPA2991': 'https://www.ti.com/lit/ds/symlink/opa2991.pdf',
    'OPA4990': 'https://www.ti.com/lit/ds/symlink/opa4990.pdf',
    'SN74LVC1G125': 'https://www.ti.com/lit/ds/symlink/sn74lvc1g125.pdf',
    'BSS138DW': 'https://www.diodes.com/assets/Datasheets/ds30203.pdf',
    'X2510WRS-02': 'https://www.lcsc.com/datasheet/C908467.pdf',
    'X2510WRS-04': 'https://www.lcsc.com/datasheet/C908468.pdf',
    'USB4205': 'https://gct.co/files/drawings/usb4205.pdf',
    '505448': 'https://www.molex.com/content/dam/molex/molex-dot-com/products/'
    'automated/en-us/salesdrawingpdf/505/505448/5054480891_sd.pdf',
    'OPA188': 'https://www.ti.com/lit/ds/symlink/opa188.pdf',
    'LM4040': 'https://www.ti.com/lit/ds/symlink/lm4040.pdf',
    'INA239': 'https://www.ti.com/lit/ds/symlink/ina239.pdf',
    'ISOW7741': 'https://www.ti.com/lit/ds/symlink/isow7741.pdf',
    'ADS1220': 'https://www.ti.com/lit/ds/symlink/ads1220.pdf',
    'AD5453': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/AD5450_5451_5452_5453.pdf',
    'TPS62822': 'https://www.ti.com/lit/ds/symlink/tps62823.pdf',
    'TPS2116': 'https://www.ti.com/lit/ds/symlink/tps2116.pdf',
    'TPD4E05U06': 'https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf',
    'NUF6401': 'https://www.onsemi.com/pdf/datasheet/nuf6401-d.pdf',
    'LSM6DSOX': 'https://www.st.com/resource/en/datasheet/lsm6dsox.pdf',
    'TPD1E05U06': 'https://www.ti.com/lit/ds/symlink/tpd1e05u06.pdf',
    'SP3422': 'https://www.littelfuse.com/assetdocs/littelfuse-tvs-diode-array-sp3422-datasheet'
    '?assetguid=21918f04-36bb-469b-8a84-152f9e3b0285',
    'AONR21307': 'https://aosmd.com/res/data_sheets/AONR21307.pdf',
    'SRP4020TA': 'https://www.bourns.com/docs/Product-Datasheets/SRP4020TA.pdf',
    'ECS-2520MV': 'https://ecsxtal.com/store/pdf/ECS-2520MV.pdf',
    'BZT52C': 'https://www.diodes.com/assets/Datasheets/ds18004.pdf',
    'MMBZ9V1': 'https://www.onsemi.com/download/data-sheet/pdf/mmbz5v6alt1-d.pdf',
    '74AHCT1G125GM': 'https://assets.nexperia.com/documents/data-sheet/74AHC_AHCT1G125.pdf',
    'SN74AHCT1G125': 'https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf',
    '74LV1T34GX': 'https://assets.nexperia.com/documents/data-sheet/74LV1T34.pdf',
    'SN74LV1T34': 'https://www.ti.com/lit/ds/symlink/sn74lv1t34.pdf',
    'SN74LVC138A': 'https://www.ti.com/lit/ds/symlink/sn74lvc138a.pdf',
    'AD9833': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/ad9833.pdf',
    'AD9837': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/AD9837.pdf',
    'LTC2954': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/2954fb.pdf',
    'ADP5071': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/ADP5071.pdf',
    'LT3097': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/lt3097.pdf',
    'SRL05P7': 'https://www.mccsemi.com/pdf/Products/SRL05P7(DFN1510-6).pdf',
    'USBLC6-2': 'https://www.st.com/resource/en/datasheet/usblc6-2.pdf',
    'AP63205': 'https://www.diodes.com/assets/Datasheets/'
    'AP63200-AP63201-AP63203-AP63205.pdf',
    'BSS138-7': 'https://www.diodes.com/assets/Datasheets/BSS138.pdf',
    'DFLS240': 'https://www.diodes.com/assets/Datasheets/DFLS240.pdf',
    'BSS84': 'https://www.onsemi.com/download/data-sheet/pdf/bss84-d.pdf',
    'ACS37800': 'https://www.allegromicro.com/-/media/files/datasheets/'
    'acs37800-datasheet.pdf',
    'USB4105': 'https://gct.co/files/drawings/usb4105.pdf',
    'SRP7050TA': 'https://www.bourns.com/docs/Product-Datasheets/SRP7050TA.pdf',
    'CR0603': 'https://www.bourns.com/docs/Product-Datasheets/chpreztr.pdf',
    '4684': 'https://cdn-shop.adafruit.com/product-files/4684/4684_WS2812B-2020_V1.3_EN.pdf',
    'XZMDKVG55W': 'https://www.sunledusa.com/products/spec/XZMDKVG55W-4.pdf',
    'WSL2512': 'https://www.vishay.com/docs/30100/wsl.pdf',
    'CRCW0603': 'https://www.vishay.com/docs/20035/dcrcwe3.pdf',
    'C0603C': 'https://content.kemet.com/datasheets/KEM_C1002_X7R_SMD.pdf',
    'C1206C': 'https://content.kemet.com/datasheets/KEM_C1002_X7R_SMD.pdf',
    'C1210C': 'https://content.kemet.com/datasheets/KEM_C1002_X7R_SMD.pdf',
    '1769': 'https://cdn-shop.adafruit.com/datasheets/17311.pdf',
    '5001': 'https://www.keyelco.com/product-pdf.cfm?p=1310',
    '4392': 'https://cdn-shop.adafruit.com/product-files/4392/'
    '4392_C13927-001_CW2001-04T-H01-BD-A.PDF',
    'TSC2046E': 'https://www.ti.com/lit/ds/symlink/tsc2046e.pdf',
    'TSC2046': 'https://www.ti.com/lit/ds/symlink/tsc2046.pdf',
    '5110': 'https://www.keyelco.com/userAssets/file/K75p60.pdf',
    'S3B-XH': 'https://www.jst-mfg.com/product/pdf/eng/eXH.pdf',
    '2305908': 'https://www.farnell.com/cad/2571341.pdf',
    '643228-1': 'https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocNm=643228&DocType=Customer+Drawing&DocLang=English',
    '1821698': 'https://www.phoenixcontact.com/en-us/products/pcb-header-mc-05-2-g-254-smd-r24-1821698?type=pdf',
}

# Phoenix item number -> product page (datasheet and drawings are on it)
PRODUCT_PAGES = {
    '4684': 'https://www.adafruit.com/product/4684',
    '1571300-2': 'https://www.digikey.com/en/products/detail/te-connectivity-alcoswitch-switches/1571300-2/2400327',
    'OPA2991IDSGR': 'https://www.ti.com/product/OPA2991',
    '505448-0891': 'https://www.molex.com/en-us/products/part-detail/5054480891',
    'SRL05P7-TP': 'https://www.digikey.com/en/products/detail/mcc-micro-commercial-components/SRL05P7-TP/12177202',
    'SP3422-04UTG': 'https://www.digikey.com/en/products/detail/littelfuse-inc/SP3422-04UTG/7897437',
    '74AHCT1G125GM,115': 'https://www.digikey.com/en/products/detail/nexperia-usa-inc/74AHCT1G125GM-115/2606148',
    '74LV1T34GXH': 'https://www.nexperia.com/pip/74LV1T34GX',
    'NUF6401MNT1G': 'https://www.digikey.com/en/products/detail/onsemi/NUF6401MNT1G/1484990',
    'LSM6DSOXTR': 'https://www.st.com/en/mems-and-sensors/lsm6dsox.html',
    'AD9837BCPZ-RL7': 'https://www.digikey.com/en/products/detail/analog-devices-inc/AD9837BCPZ-RL7/2700194',
    'ECS-2520MV-160-BN-TR': 'https://www.digikey.com/en/products/detail/ecs-inc/ECS-2520MV-160-BN-TR/13968073',
    'EVP-AA802Q': 'https://www.digikey.com/en/products/detail/panasonic-industry/EVP-AA802Q/2810553',
    'APGB0607G22R23C': 'https://www.digikey.com/en/products/detail/kingbright/APGB0607G22R23C/22561020',
    'EVQ-P2F02K': 'https://www.mouser.com/en/ProductDetail/Panasonic-Industry/EVQ-P2F02K',
    'SWR25X-NRTC-S02-RB-BA':'https://www.digikey.com/en/products/detail/sullins-connector-solutions/SWR25X-NRTC-S02-RB-BA/2769660',
    '61900311021': 'https://www.digikey.com/en/products/detail/w%C3%BCrth-elektronik/61900311021/2508469',
    'CO975': 'https://www.moddiy.com/products/5408/4-Pin-3-Pin-2.54mm-Pitch-2510-Fan-Male-Angled-Connector-Black.html',
    'X2510WRS-02-9TSN': 'https://www.lcsc.com/product-detail/C908467.html',
    'X2510WRS-04-9TSN': 'https://www.lcsc.com/product-detail/C908468.html',
    'USB4205-GF-A': 'https://www.digikey.com/en/products/detail/gct/USB4205-GF-A/24625573',
    '2305908-2': 'https://www.digikey.com/en/products/detail/te-connectivity-amp-connectors/2305908-2/9744703',
    '643228-1': 'https://www.digikey.com/en/products/detail/te-connectivity-amp-connectors/643228-1/297685',
    '1821698': 'https://www.digikey.com/en/products/detail/phoenix-contact/1821698/7558295',
    '1769': 'https://www.adafruit.com/product/1769',
    '5001': 'https://www.keyelco.com/product.cfm/product_id/1310',
    '4392': 'https://www.adafruit.com/product/4392',
}


def product_url(mpn):
    """Product page for a manufacturer part number.

    @param mpn manufacturer part number
    @return maker product page if listed, else the Digi-Key search for it
    """
    if mpn in PRODUCT_PAGES:
        return PRODUCT_PAGES[mpn]
    return 'https://www.digikey.com/en/products/result?keywords=' + quote(mpn)


def datasheet_url(mpn):
    """Datasheet for a part number, falling back to its product page."""
    matches = [prefix for prefix in DATASHEETS if mpn.startswith(prefix)]
    if matches:
        return DATASHEETS[max(matches, key=len)]
    return product_url(mpn)


def links(ref, value, footprint):
    """{'Datasheet': url, 'Product': url} for one part, or {} if it has no
    orderable part (test points, parts without a chosen MPN).
    """
    if ref.startswith('#') or 'TestPoint_Pad' in footprint:
        return {}
    name = footprint.split(':')[-1]
    _maker, mpn, *_rest = gen_bom.resolve(
        gen_bom.bom_value(ref, value, name), name
    )
    if not mpn:
        return {}
    return {'Datasheet': datasheet_url(mpn), 'Product': product_url(mpn)}
