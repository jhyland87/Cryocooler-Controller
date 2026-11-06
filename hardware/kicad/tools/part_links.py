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
    'ESP32-S3-WROOM-2': 'https://www.espressif.com/sites/default/files/'
    'documentation/esp32-s3-wroom-2_datasheet_en.pdf',
    'OPA1655': 'https://www.ti.com/lit/ds/symlink/opa1656.pdf',
    '54-00164': 'https://www.digikey.com/en/products/detail/tensility/54-00164/10459298',
    'MJ-3523': 'https://www.sameskydevices.com/product/resource/mj-3523-smt.pdf',
    '61900311021': 'https://www.we-online.com/components/products/datasheet/61900311021.pdf',
    'SWR25X': 'https://static.datasheets.com/doc/20841721-sullins-swr25x-nrtc-s20-st-ba-ds.pdf',
    'OPA188': 'https://www.ti.com/lit/ds/symlink/opa188.pdf',
    'LM4040': 'https://www.ti.com/lit/ds/symlink/lm4040.pdf',
    'INA239': 'https://www.ti.com/lit/ds/symlink/ina239.pdf',
    'ISO7741': 'https://www.ti.com/lit/ds/symlink/iso7741.pdf',
    'ADS1220': 'https://www.ti.com/lit/ds/symlink/ads1220.pdf',
    'SN74AHCT1G125': 'https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf',
    '74LVC1G125': 'https://www.ti.com/lit/ds/symlink/sn74lvc1g125.pdf',
    'SN74LV1T34': 'https://www.ti.com/lit/ds/symlink/sn74lv1t34.pdf',
    'SN74LVC138A': 'https://www.ti.com/lit/ds/symlink/sn74lvc138a.pdf',
    'AD9833': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/ad9833.pdf',
    'AD633': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/AD633.pdf',
    'LTC2954': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/2954fb.pdf',
    'ADP5071': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/ADP5071.pdf',
    'LT3097': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/lt3097.pdf',
    'SC18IS604': 'https://www.nxp.com/docs/en/data-sheet/SC18IS604.pdf',
    'CL25': 'https://ww1.microchip.com/downloads/en/DeviceDoc/CL25.pdf',
    'MCP4921': 'https://ww1.microchip.com/downloads/en/DeviceDoc/22248a.pdf',
    'EMC2303': 'https://ww1.microchip.com/downloads/en/DeviceDoc/'
    'EMC2301-2-3-5-Data-Sheet-DS20006532A.pdf',
    'USBLC6-2': 'https://www.st.com/resource/en/datasheet/usblc6-2.pdf',
    'LD1117': 'https://www.st.com/resource/en/datasheet/ld1117.pdf',
    'LM66100': 'https://www.ti.com/lit/ds/symlink/lm66100.pdf',
    'AP63205': 'https://www.diodes.com/assets/Datasheets/'
    'AP63200-AP63201-AP63203-AP63205.pdf',
    'BSS138-7': 'https://www.diodes.com/assets/Datasheets/BSS138.pdf',
    'DFLS240': 'https://www.diodes.com/assets/Datasheets/DFLS240.pdf',
    'BSS84': 'https://www.onsemi.com/download/data-sheet/pdf/bss84-d.pdf',
    'ACS37800': 'https://www.allegromicro.com/-/media/files/datasheets/'
    'acs37800-datasheet.pdf',
    'USB4105': 'https://gct.co/files/drawings/usb4105.pdf',
    'SRP7050TA': 'https://www.bourns.com/docs/Product-Datasheets/SRP7050TA.pdf',
    'SRP6050CA': 'https://www.bourns.com/docs/Product-Datasheets/SRP6050CA.pdf',
    'CR0603': 'https://www.bourns.com/docs/Product-Datasheets/chpreztr.pdf',
    '1655': 'https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf',
    'XZMDKVG55W': 'https://www.sunledusa.com/products/spec/XZMDKVG55W-4.pdf',
    'WSL2512': 'https://www.vishay.com/docs/30100/wsl.pdf',
    'CRCW0603': 'https://www.vishay.com/docs/20035/dcrcwe3.pdf',
    'C0603C': 'https://content.kemet.com/datasheets/KEM_C1002_X7R_SMD.pdf',
    'C1206C': 'https://content.kemet.com/datasheets/KEM_C1002_X7R_SMD.pdf',
    'C1210C': 'https://content.kemet.com/datasheets/KEM_C1002_X7R_SMD.pdf',
    'T491': 'https://content.kemet.com/datasheets/KEM_T2005_T491.pdf',
    'SG-8002CA': 'https://www.digikey.com/en/products/result?keywords='
    'SG-8002CA',
    '1769': 'https://cdn-shop.adafruit.com/datasheets/17311.pdf',
    '5001': 'https://www.keyelco.com/product-pdf.cfm?p=1310',
    '4392': 'https://cdn-shop.adafruit.com/product-files/4392/'
    '4392_C13927-001_CW2001-04T-H01-BD-A.PDF',
    'LT8582': 'https://www.analog.com/media/en/technical-documentation/'
    'data-sheets/8582f.pdf',
    'TSC2046E': 'https://www.ti.com/lit/ds/symlink/tsc2046e.pdf',
    'TSC2046': 'https://www.ti.com/lit/ds/symlink/tsc2046.pdf',
    '5110': 'https://www.keyelco.com/userAssets/file/K75p60.pdf',
    'S3B-XH': 'https://www.jst-mfg.com/product/pdf/eng/eXH.pdf',
    '2305908': 'https://www.farnell.com/cad/2571341.pdf',
    '1821698': 'https://www.phoenixcontact.com/en-us/products/pcb-header-mc-05-2-g-254-smd-r24-1821698?type=pdf',
}

# Phoenix item number -> product page (datasheet and drawings are on it)
PRODUCT_PAGES = {
    'SWR25X-NRTC-S02-RB-BA': 'https://www.digikey.com/en/products/detail/sullins-connector-solutions/SWR25X-NRTC-S02-RB-BA/2769660',
    '61900311021': 'https://www.digikey.com/en/products/detail/w%C3%BCrth-elektronik/61900311021/2508469',
    'CO975': 'https://www.moddiy.com/products/5408/4-Pin-3-Pin-2.54mm-Pitch-2510-Fan-Male-Angled-Connector-Black.html',
    '2305908-2': 'https://www.digikey.com/en/products/detail/te-connectivity-amp-connectors/2305908-2/9744703',
    '2305908-3': 'https://www.digikey.com/en/products/detail/te-connectivity-amp-connectors/2305908-3/7561707',
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
