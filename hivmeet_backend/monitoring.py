"""
Monitoring and alerting tools for HIVMeet.
File: hivmeet_backend/monitoring.py
"""
import time
import psutil
import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.core.mail import mail_admins
from datetime import timedelta
import json

logger = logging.getLogger('hivmeet.monitoring')


class HealthCheck:
    """System health checks."""
    
    @staticmethod
    def check_database():
        """Check database connectivity and performance."""
        try:
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            response_time = time.time() - start
            
            return {
                'status': 'healthy' if response_time < 0.1 else 'degraded',
                'response_time': response_time,
                'message': 'Database responding normally' if response_time < 0.1 else 'Database slow'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'response_time': None,
                'message': str(e)
            }
    
    @staticmethod
    def check_cache():
        """Check cache connectivity."""
        try:
            test_key = 'health_check_test'
            test_value = timezone.now().isoformat()
            
            cache.set(test_key, test_value, 10)
            retrieved = cache.get(test_key)
            cache.delete(test_key)
            
            return {
                'status': 'healthy' if retrieved == test_value else 'unhealthy',
                'message': 'Cache working properly' if retrieved == test_value else 'Cache not working'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': str(e)
            }
    
    @staticmethod
    def check_system_resources():
        """Check system resource usage."""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status = 'healthy'
        issues = []
        
        if cpu_percent > 80:
            status = 'degraded'
            issues.append(f'High CPU usage: {cpu_percent}%')
        
        if memory.percent > 85:
            status = 'degraded'
            issues.append(f'High memory usage: {memory.percent}%')
        
        if disk.percent > 90:
            status = 'unhealthy'
            issues.append(f'Low disk space: {disk.percent}% used')
        
        return {
            'status': status,
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk.percent,
            'message': ', '.join(issues) if issues else 'System resources normal'
        }


class MetricsCollector:
    """Collect and store application metrics."""
    
    @staticmethod
    def record_request_metric(view_name, method, status_code, response_time):
        """Record API request metrics."""
        cache_key = f'metrics:requests:{timezone.now().strftime("%Y%m%d%H")}'
        metrics = cache.get(cache_key, {})
        
        endpoint_key = f'{method}:{view_name}'
        if endpoint_key not in metrics:
            metrics[endpoint_key] = {
                'count': 0,
                'errors': 0,
                'total_time': 0,
                'status_codes': {}
            }
        
        metrics[endpoint_key]['count'] += 1
        metrics[endpoint_key]['total_time'] += response_time
        
        status_key = str(status_code)
        metrics[endpoint_key]['status_codes'][status_key] = \
            metrics[endpoint_key]['status_codes'].get(status_key, 0) + 1
        
        if status_code >= 400:
            metrics[endpoint_key]['errors'] += 1
        
        cache.set(cache_key, metrics, 3600 * 25)  # Keep for 25 hours
    
    @staticmethod
    def get_metrics_summary(hours=24):
        """Get metrics summary for the last N hours."""
        summary = {
            'endpoints': {},
            'total_requests': 0,
            'total_errors': 0,
            'average_response_time': 0
        }
        
        now = timezone.now()
        total_time = 0
        
        for i in range(hours):
            hour = now - timedelta(hours=i)
            cache_key = f'metrics:requests:{hour.strftime("%Y%m%d%H")}'
            metrics = cache.get(cache_key, {})
            
            for endpoint, data in metrics.items():
                if endpoint not in summary['endpoints']:
                    summary['endpoints'][endpoint] = {
                        'count': 0,
                        'errors': 0,
                        'average_time': 0,
                        'status_codes': {}
                    }
                
                summary['endpoints'][endpoint]['count'] += data['count']
                summary['endpoints'][endpoint]['errors'] += data['errors']
                
                for status, count in data['status_codes'].items():
                    summary['endpoints'][endpoint]['status_codes'][status] = \
                        summary['endpoints'][endpoint]['status_codes'].get(status, 0) + count
                
                summary['total_requests'] += data['count']
                summary['total_errors'] += data['errors']
                total_time += data['total_time']
        
        if summary['total_requests'] > 0:
            summary['average_response_time'] = total_time / summary['total_requests']
        
        # Calculate average times for endpoints
        for endpoint, data in summary['endpoints'].items():
            if data['count'] > 0:
                # Get total time from hourly data
                endpoint_total_time = 0
                for i in range(hours):
                    hour = now - timedelta(hours=i)
                    cache_key = f'metrics:requests:{hour.strftime("%Y%m%d%H")}'
                    hourly_metrics = cache.get(cache_key, {})
                    if endpoint in hourly_metrics:
                        endpoint_total_time += hourly_metrics[endpoint]['total_time']
                
                data['average_time'] = endpoint_total_time / data['count']
        
        return summary


class AlertManager:
    """Manage system alerts."""
    
    THRESHOLDS = {
        'error_rate': 0.05,  # 5% error rate
        'response_time': 1.0,  # 1 second average
        'cpu_usage': 80,  # 80% CPU
        'memory_usage': 85,  # 85% memory
        'disk_usage': 90,  # 90% disk
    }
    
    @staticmethod
    def check_alerts():
        """Check system metrics and send alerts if needed."""
        alerts = []
        
        # Check health
        health_checks = {
            'database': HealthCheck.check_database(),
            'cache': HealthCheck.check_cache(),
            'system': HealthCheck.check_system_resources()
        }
        
        for component, status in health_checks.items():
            if status['status'] == 'unhealthy':
                alerts.append({
                    'severity': 'critical',
                    'component': component,
                    'message': status['message']
                })
            elif status['status'] == 'degraded':
                alerts.append({
                    'severity': 'warning',
                    'component': component,
                    'message': status['message']
                })
        
        # Check metrics
        metrics = MetricsCollector.get_metrics_summary(hours=1)
        
        if metrics['total_requests'] > 0:
            error_rate = metrics['total_errors'] / metrics['total_requests']
            if error_rate > AlertManager.THRESHOLDS['error_rate']:
                alerts.append({
                    'severity': 'warning',
                    'component': 'api',
                    'message': f'High error rate: {error_rate:.2%}'
                })
        
        if metrics['average_response_time'] > AlertManager.THRESHOLDS['response_time']:
            alerts.append({
                'severity': 'warning',
                'component': 'performance',
                'message': f'Slow response times: {metrics["average_response_time"]:.2f}s average'
            })
        
        # Send alerts
        if alerts:
            AlertManager.send_alerts(alerts)
        
        return alerts
    
    @staticmethod
    def send_alerts(alerts):
        """Send alerts to administrators."""
        # Group by severity
        critical = [a for a in alerts if a['severity'] == 'critical']
        warnings = [a for a in alerts if a['severity'] == 'warning']
        
        message = "HIVMeet System Alerts\n\n"
        
        if critical:
            message += "CRITICAL ALERTS:\n"
            for alert in critical:
                message += f"- [{alert['component']}] {alert['message']}\n"
            message += "\n"
        
        if warnings:
            message += "WARNINGS:\n"
            for alert in warnings:
                message += f"- [{alert['component']}] {alert['message']}\n"
        
        # Send email to admins
        if critical:
            mail_admins('CRITICAL: HIVMeet System Alert', message, fail_silently=True)
        
        # Log all alerts
        logger.warning(f"System alerts detected: {json.dumps(alerts)}")


# Management command for monitoring
class Command(BaseCommand):
    """
    Management command for system monitoring.
    File: management/commands/monitor_system.py
    """
    help = 'Monitor system health and send alerts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuous monitoring'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=300,
            help='Check interval in seconds (default: 300)'
        )
    
    def handle(self, *args, **options):
        if options['continuous']:
            self.stdout.write('Starting continuous monitoring...')
            while True:
                self.run_checks()
                time.sleep(options['interval'])
        else:
            self.run_checks()
    
    def run_checks(self):
        """Run all system checks."""
        self.stdout.write(f'\n[{timezone.now()}] Running system checks...')
        
        # Health checks
        health = {
            'database': HealthCheck.check_database(),
            'cache': HealthCheck.check_cache(),
            'system': HealthCheck.check_system_resources()
        }
        
        for component, status in health.items():
            status_color = {
                'healthy': self.style.SUCCESS,
                'degraded': self.style.WARNING,
                'unhealthy': self.style.ERROR
            }[status['status']]
            
            self.stdout.write(
                f'{component}: {status_color(status["status"])} - {status["message"]}'
            )
        
        # Metrics
        metrics = MetricsCollector.get_metrics_summary(hours=1)
        self.stdout.write(
            f'\nMetrics (last hour):\n'
            f'  Total requests: {metrics["total_requests"]}\n'
            f'  Total errors: {metrics["total_errors"]}\n'
            f'  Average response time: {metrics["average_response_time"]:.3f}s'
        )
        
        # Check alerts
        alerts = AlertManager.check_alerts()
        if alerts:
            self.stdout.write(self.style.WARNING(f'\nAlerts: {len(alerts)} active'))
            for alert in alerts:
                self.stdout.write(
                    f'  [{alert["severity"]}] {alert["component"]}: {alert["message"]}'
                )