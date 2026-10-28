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
    'OPA1656': 'https://www.ti.com/lit/ds/symlink/opa1656.pdf',
    'OPA188': 'https://www.ti.com/lit/ds/symlink/opa188.pdf',
    'LM4040': 'https://www.ti.com/lit/ds/symlink/lm4040.pdf',
    'INA239': 'https://www.ti.com/lit/ds/symlink/ina239.pdf',
    'ISO7741': 'https://www.ti.com/lit/ds/symlink/iso7741.pdf',
    'ADS1220': 'https://www.ti.com/lit/ds/symlink/ads1220.pdf',
    'SN74AHCT1G125': 'https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf',
    '74LVC1G125': 'https://www.ti.com/lit/ds/symlink/sn74lvc1g125.pdf',
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
    '5054480871': 'https://www.molex.com/content/dam/molex/molex-dot-com/'
    'products/automated/en-us/salesdrawingpdf/505/505448/5054480871_sd.pdf',
    'DF13-': 'https://www.hirose.com/api/v1/series/DF13/documents/'
    'product_series_catalog/content?lang=EN',
    'S3B-XH': 'https://www.jst-mfg.com/product/pdf/eng/eXH.pdf',
    'S4B-XH': 'https://www.jst-mfg.com/product/pdf/eng/eXH.pdf',
}

# Phoenix item number -> product page (datasheet and drawings are on it)
PRODUCT_PAGES = {
    '1757242': 'https://www.phoenixcontact.com/en-us/products/'
    'pcb-header-mstba-25-2-g-508-1757242',
    '1803277': 'https://www.phoenixcontact.com/en-us/products/'
    'pcb-header-mc-15-2-g-381-1803277',
    '5054480871': 'https://www.molex.com/en-us/products/part-detail/5054480871',
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
    if ref.startswith(('#', 'TP')):
        return {}
    name = footprint.split(':')[-1]
    _maker, mpn, *_rest = gen_bom.resolve(
        gen_bom.bom_value(ref, value, name), name
    )
    if not mpn:
        return {}
    return {'Datasheet': datasheet_url(mpn), 'Product': product_url(mpn)}
