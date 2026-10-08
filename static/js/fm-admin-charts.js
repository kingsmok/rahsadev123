/* ═══════════════════════════════════════════════════════════════════════
   پنل مدیریت فایل‌مارکت — نمودارها (Chart.js 4)
   ── داده از {{ chart_data|json_script }} خوانده می‌شود
   ── رنگ‌ها از همان توکن‌های CSS پوسته گرفته می‌شوند تا حالت شب خودکار باشد
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    var PALETTE = ['#46a9ae', '#f4703f', '#6f5bd6', '#2c7fb8', '#1f9d63', '#c98a04', '#d24848', '#7acfd4'];

    function readData() {
        var node = document.getElementById('ap-chart-data');
        if (!node) {
            return null;
        }
        try {
            return JSON.parse(node.textContent);
        } catch (error) {
            return null;
        }
    }

    function cssVar(name, fallback) {
        var value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return value || fallback;
    }

    function toPersianDigits(value) {
        return String(value).replace(/[0-9]/g, function (digit) {
            return '۰۱۲۳۴۵۶۷۸۹'[Number(digit)];
        });
    }

    function formatNumber(value) {
        return toPersianDigits(Number(value || 0).toLocaleString('en-US'));
    }

    function themeColors() {
        return {
            text: cssVar('--ap-text-soft', '#4a5b6b'),
            muted: cssVar('--ap-muted', '#7d8ea0'),
            grid: cssVar('--ap-border', '#e4eaf1'),
            surface: cssVar('--ap-surface', '#ffffff'),
            primary: cssVar('--ap-primary', '#46a9ae'),
            accent: cssVar('--ap-accent', '#f4703f')
        };
    }

    function isEmpty(values) {
        return !values || !values.length || values.every(function (value) {
            return !value;
        });
    }

    function showEmpty(canvas, message) {
        var wrap = canvas.parentElement;
        if (!wrap) {
            return;
        }
        wrap.innerHTML = '<div class="ap-empty"><i class="fa-solid fa-chart-simple" aria-hidden="true"></i>' +
            message + '</div>';
    }

    function applyDefaults(colors) {
        if (!window.Chart) {
            return;
        }
        Chart.defaults.font.family = "'Vazirmatn FD', Tahoma, sans-serif";
        Chart.defaults.font.size = 11.5;
        Chart.defaults.color = colors.text;
        Chart.defaults.plugins.tooltip.rtl = true;
        Chart.defaults.plugins.tooltip.textDirection = 'rtl';
        Chart.defaults.plugins.tooltip.backgroundColor = '#0f1c26';
        Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
        Chart.defaults.plugins.tooltip.bodyColor = '#dbe6ef';
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.cornerRadius = 10;
        Chart.defaults.plugins.tooltip.titleFont = { weight: '700', size: 12 };
        Chart.defaults.maintainAspectRatio = false;
    }

    function revenueChart(colors) {
        var canvas = document.getElementById('apRevenueChart');
        var data = window.__fmChartData && window.__fmChartData.revenue;
        if (!canvas || !data) {
            return null;
        }
        if (isEmpty(data.values) && isEmpty(data.orders)) {
            showEmpty(canvas, 'در این بازه فروشی ثبت نشده است.');
            return null;
        }

        var context = canvas.getContext('2d');
        var gradient = context.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight || 260);
        gradient.addColorStop(0, 'rgba(70, 169, 174, .35)');
        gradient.addColorStop(1, 'rgba(70, 169, 174, 0)');

        return new Chart(canvas, {
            data: {
                labels: data.labels,
                datasets: [
                    {
                        type: 'line',
                        label: 'درآمد (تومان)',
                        data: data.values,
                        borderColor: colors.primary,
                        backgroundColor: gradient,
                        borderWidth: 2.5,
                        tension: .35,
                        fill: true,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        pointBackgroundColor: colors.primary,
                        yAxisID: 'y'
                    },
                    {
                        type: 'bar',
                        label: 'تعداد سفارش',
                        data: data.orders,
                        backgroundColor: 'rgba(244, 112, 63, .55)',
                        hoverBackgroundColor: colors.accent,
                        borderRadius: 6,
                        maxBarThickness: 16,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                interaction: { mode: 'index', intersect: false },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: colors.muted, maxRotation: 0, autoSkipPadding: 18, callback: function (value, index) { return toPersianDigits(this.getLabelForValue(value)); } }
                    },
                    y: {
                        position: 'right',
                        grid: { color: colors.grid, drawTicks: false },
                        border: { display: false },
                        ticks: { color: colors.muted, callback: function (value) { return formatNumber(value); } }
                    },
                    y1: {
                        position: 'left',
                        grid: { display: false },
                        border: { display: false },
                        ticks: { color: colors.muted, precision: 0, callback: function (value) { return toPersianDigits(value); } }
                    }
                },
                plugins: {
                    legend: { display: true, position: 'bottom', rtl: true, labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle', padding: 16 } },
                    tooltip: {
                        callbacks: {
                            label: function (item) {
                                if (item.dataset.yAxisID === 'y1') {
                                    return ' ' + item.dataset.label + ': ' + toPersianDigits(item.parsed.y) + ' سفارش';
                                }
                                return ' ' + item.dataset.label + ': ' + formatNumber(item.parsed.y) + ' تومان';
                            }
                        }
                    }
                }
            }
        });
    }

    function statusChart(colors) {
        var canvas = document.getElementById('apStatusChart');
        var data = window.__fmChartData && window.__fmChartData.status;
        if (!canvas || !data) {
            return null;
        }
        if (isEmpty(data.values)) {
            showEmpty(canvas, 'هنوز سفارشی ثبت نشده است.');
            return null;
        }

        var legend = document.getElementById('apStatusLegend');
        if (legend) {
            legend.innerHTML = data.labels.map(function (label, index) {
                return '<li><span class="ap-legend__dot" style="background:' + PALETTE[index % PALETTE.length] + '"></span>' +
                    label + '<b class="ap-num">' + toPersianDigits(data.values[index]) + '</b></li>';
            }).join('');
        }

        return new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: PALETTE,
                    borderColor: colors.surface,
                    borderWidth: 3,
                    hoverOffset: 8
                }]
            },
            options: {
                cutout: '62%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (item) {
                                return ' ' + item.label + ': ' + toPersianDigits(item.parsed) + ' سفارش';
                            }
                        }
                    }
                }
            }
        });
    }

    function typeChart(colors) {
        var canvas = document.getElementById('apTypeChart');
        var data = window.__fmChartData && window.__fmChartData.productType;
        if (!canvas || !data) {
            return null;
        }
        if (isEmpty(data.values)) {
            showEmpty(canvas, 'داده‌ای برای نمایش وجود ندارد.');
            return null;
        }

        return new Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'درآمد (تومان)',
                    data: data.values,
                    backgroundColor: 'rgba(70, 169, 174, .75)',
                    hoverBackgroundColor: colors.primary,
                    borderRadius: 8,
                    maxBarThickness: 26
                }]
            },
            options: {
                indexAxis: 'y',
                scales: {
                    x: {
                        grid: { color: colors.grid, drawTicks: false },
                        border: { display: false },
                        ticks: { color: colors.muted, callback: function (value) { return formatNumber(value); } }
                    },
                    y: {
                        grid: { display: false },
                        border: { display: false },
                        ticks: { color: colors.text }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (item) {
                                return ' درآمد: ' + formatNumber(item.parsed.x) + ' تومان';
                            }
                        }
                    }
                }
            }
        });
    }

    function destroyCharts() {
        (window.__fmCharts || []).forEach(function (chart) {
            if (chart) {
                chart.destroy();
            }
        });
        window.__fmCharts = [];
    }

    function render() {
        if (!window.Chart) {
            return;
        }
        destroyCharts();
        var colors = themeColors();
        applyDefaults(colors);
        window.__fmCharts = [revenueChart(colors), statusChart(colors), typeChart(colors)];
    }

    document.addEventListener('DOMContentLoaded', function () {
        window.__fmChartData = readData();
        render();

        var timer = null;
        document.addEventListener('fm-theme-change', function () {
            clearTimeout(timer);
            timer = setTimeout(render, 60);
        });

        window.addEventListener('resize', function () {
            clearTimeout(timer);
            timer = setTimeout(function () {
                (window.__fmCharts || []).forEach(function (chart) {
                    if (chart) {
                        chart.resize();
                    }
                });
            }, 160);
        });
    });
})();
