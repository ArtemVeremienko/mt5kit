/**
 * TradingView-Style Interactive Crosshair Cursor & Axis Badges for Plotly.js
 *
 * Modern ECMAScript (ES2022+) module with Temporal API & Intl integration.
 * Provides real-time bidirectional cursor tracking (dashed crosshairs),
 * precise time/date coordinate badges, and price coordinate badges across
 * all decoupled subplots in the Multi-Timeframe History Viewer.
 */
function initTradingViewCursor(options = {}) {
    const theme = (options.theme ?? 'dark').toLowerCase();
    const isDark = theme === 'dark';
    const defaultDigits = typeof options.digits === 'number' ? options.digits : null;

    // Use explicit color overrides if provided; otherwise fallback to theme defaults
    const lineColor = options.lineColor ?? options.line_color ?? (isDark ? 'rgba(120, 123, 134, 0.75)' : 'rgba(100, 116, 139, 0.75)');
    const timeBg = options.timeBg ?? options.time_bg ?? (isDark ? '#1e222d' : '#f0f3fa');
    const timeColor = options.timeColor ?? options.time_color ?? (isDark ? '#d1d4dc' : '#131722');
    const timeBorder = options.timeBorder ?? options.time_border ?? (isDark ? '1px solid #434651' : '1px solid #d1d4dc');
    const priceBg = options.priceBg ?? options.price_bg ?? '#2962FF';
    const priceColor = options.priceColor ?? options.price_color ?? '#ffffff';

    const gd = document.querySelector(options.selector ?? '.plotly-graph-div');
    if (!gd) return;

    const container = gd.parentElement ?? gd;
    container.style.position = 'relative';

    // Inject CSS styles for clean full-bleed layout and crosshair cursor
    const styleId = 'tradingview-cursor-style';
    if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            html, body {
                margin: 0 !important;
                padding: 0 !important;
            }
            .plotly-graph-div .draglayer, .plotly-graph-div .nsewdrag, .plotly-graph-div .cursor-crosshair {
                cursor: crosshair !important;
            }
        `;
        document.head.appendChild(style);
    }

    // Helper to create positioned badge elements
    const createBadge = (styles) => {
        const el = document.createElement('div');
        Object.assign(el.style, {
            position: 'absolute',
            display: 'none',
            pointerEvents: 'none',
            zIndex: '1000',
            whiteSpace: 'nowrap',
            boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
            ...styles
        });
        container.appendChild(el);
        return el;
    };

    // Vertical Cursor Line
    const vLine = document.createElement('div');
    Object.assign(vLine.style, {
        position: 'absolute',
        display: 'none',
        width: '0px',
        borderLeft: `1px dashed ${lineColor}`,
        pointerEvents: 'none',
        zIndex: '990'
    });
    container.appendChild(vLine);

    // Horizontal Cursor Line
    const hLine = document.createElement('div');
    Object.assign(hLine.style, {
        position: 'absolute',
        display: 'none',
        height: '0px',
        borderTop: `1px dashed ${lineColor}`,
        pointerEvents: 'none',
        zIndex: '990'
    });
    container.appendChild(hLine);

    // Time Badge (X-Axis)
    const timeBadge = createBadge({
        backgroundColor: timeBg,
        color: timeColor,
        border: timeBorder,
        padding: '2px 6px',
        borderRadius: '3px',
        fontSize: '11px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif',
        transform: 'translateX(-50%)'
    });

    // Price Badge (Y-Axis)
    const priceBadge = createBadge({
        backgroundColor: priceBg,
        color: priceColor,
        padding: '2px 6px',
        borderRadius: '3px',
        fontSize: '11px',
        fontWeight: '500',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif',
        transform: 'translateY(-50%)'
    });

    const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    /**
     * Formats timestamp coordinate using ECMAScript Temporal API if supported,
     * with standard Date/regex ISO parser fallback.
     */
    const formatTime = (val, isDaily = false) => {
        if (!val) return '';

        // 1. Leverage native Temporal API when supported in modern JavaScript runtimes
        if (typeof Temporal !== 'undefined') {
            try {
                let dt;
                if (typeof val === 'number') {
                    dt = Temporal.Instant.fromEpochMilliseconds(val).toZonedDateTimeISO('UTC').toPlainDateTime();
                } else {
                    const cleanIso = String(val).trim().replace(' ', 'T');
                    dt = Temporal.PlainDateTime.from(cleanIso);
                }

                const day = dt.day;
                const month = MONTH_NAMES[dt.month - 1];
                const year = String(dt.year).slice(-2);

                if (isDaily || (dt.hour === 0 && dt.minute === 0 && dt.second === 0 && dt.millisecond === 0)) {
                    return `${day} ${month} '${year}`;
                }

                const hh = String(dt.hour).padStart(2, '0');
                const mm = String(dt.minute).padStart(2, '0');
                const ss = String(dt.second).padStart(2, '0');
                const ms = dt.millisecond ? String(dt.millisecond).padStart(3, '0') : '';

                if (ms && ms !== '000') return `${day} ${month} '${year}  ${hh}:${mm}:${ss}.${ms}`;
                if (ss !== '00') return `${day} ${month} '${year}  ${hh}:${mm}:${ss}`;
                return `${day} ${month} '${year}  ${hh}:${mm}`;
            } catch (_) {
                // Fallback to regex/Date if Temporal throws on non-standard input
            }
        }

        // 2. Standard Fast ISO Parser Fallback
        const str = String(val).trim();
        const m = str.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?/);
        if (m) {
            const [, y, mo, d, hrs, mins, secs, frac] = m;
            const year = y.slice(-2);
            const month = MONTH_NAMES[parseInt(mo, 10) - 1] ?? mo;
            const day = parseInt(d, 10);

            if (isDaily || !hrs) return `${day} ${month} '${year}`;

            const ms = frac ? frac.slice(0, 3) : '';
            if (ms && ms !== '000') return `${day} ${month} '${year}  ${hrs}:${mins}:${secs ?? '00'}.${ms}`;
            if (secs && secs !== '00') return `${day} ${month} '${year}  ${hrs}:${mins}:${secs}`;
            return `${day} ${month} '${year}  ${hrs}:${mins}`;
        }

        // 3. Numeric Epoch Milliseconds Fallback
        const num = Number(val);
        if (!Number.isNaN(num)) {
            const d = new Date(num);
            const pad = (n) => String(n).padStart(2, '0');
            const day = d.getUTCDate();
            const month = MONTH_NAMES[d.getUTCMonth()];
            const year = String(d.getUTCFullYear()).slice(-2);
            const hrs = pad(d.getUTCHours());
            const mins = pad(d.getUTCMinutes());
            const secs = pad(d.getUTCSeconds());
            const ms = String(d.getUTCMilliseconds()).padStart(3, '0');

            if (isDaily) return `${day} ${month} '${year}`;
            if (ms !== '000') return `${day} ${month} '${year}  ${hrs}:${mins}:${secs}.${ms}`;
            if (secs !== '00') return `${day} ${month} '${year}  ${hrs}:${mins}:${secs}`;
            return `${day} ${month} '${year}  ${hrs}:${mins}`;
        }

        return str;
    };

    /**
     * Formats price value with exact symbol decimal precision.
     */
    const formatPrice = (val, digits = defaultDigits) => {
        const num = Number(val);
        if (Number.isNaN(num)) return String(val);
        if (typeof digits === 'number' && digits >= 0) {
            return num.toFixed(digits);
        }
        return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 5 });
    };

    const getSubplotAxisPairs = () => {
        if (!gd._fullLayout) return [];
        const pairs = [];
        for (const key of Object.keys(gd._fullLayout)) {
            if (/^xaxis\d*$/.test(key)) {
                const suffix = key.replace('xaxis', '');
                const yKey = `yaxis${suffix}`;
                if (gd._fullLayout[yKey]) {
                    pairs.push({
                        xa: gd._fullLayout[key],
                        ya: gd._fullLayout[yKey],
                        isDaily: key === 'xaxis'
                    });
                }
            }
        }
        return pairs;
    };

    gd.addEventListener('mousemove', (e) => {
        const pairs = getSubplotAxisPairs();
        if (!pairs.length) return;

        const rect = gd.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const activePair = pairs.find((p) => (
            mouseX >= p.xa._offset && mouseX <= p.xa._offset + p.xa._length &&
            mouseY >= p.ya._offset && mouseY <= p.ya._offset + p.ya._length
        ));

        if (activePair) {
            const { xa, ya, isDaily } = activePair;

            const xVal = xa.p2d ? xa.p2d(mouseX - xa._offset) : (xa.p2c ? xa.p2c(mouseX - xa._offset) : null);
            const yVal = ya.p2d ? ya.p2d(mouseY - ya._offset) : (ya.p2c ? ya.p2c(mouseY - ya._offset) : null);

            // Update Vertical Line bounded to active subplot
            vLine.style.left = `${mouseX}px`;
            vLine.style.top = `${ya._offset}px`;
            vLine.style.height = `${ya._length}px`;
            vLine.style.display = 'block';

            // Update Horizontal Line bounded to active subplot
            hLine.style.top = `${mouseY}px`;
            hLine.style.left = `${xa._offset}px`;
            hLine.style.width = `${xa._length}px`;
            hLine.style.display = 'block';

            // Update Time Badge on bottom of active subplot
            timeBadge.textContent = formatTime(xVal, isDaily);
            timeBadge.style.left = `${mouseX}px`;
            timeBadge.style.top = `${ya._offset + ya._length + 2}px`;
            timeBadge.style.display = 'block';

            // Update Price Badge on right of active subplot
            priceBadge.textContent = formatPrice(yVal);
            priceBadge.style.top = `${mouseY}px`;
            priceBadge.style.left = `${xa._offset + xa._length + 2}px`;
            priceBadge.style.display = 'block';
        } else {
            vLine.style.display = 'none';
            hLine.style.display = 'none';
            timeBadge.style.display = 'none';
            priceBadge.style.display = 'none';
        }
    });

    gd.addEventListener('mouseleave', () => {
        vLine.style.display = 'none';
        hLine.style.display = 'none';
        timeBadge.style.display = 'none';
        priceBadge.style.display = 'none';
    });
}
