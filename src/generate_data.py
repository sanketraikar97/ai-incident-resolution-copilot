"""
Synthetic data generator for the AI Incident Resolution Copilot.
Run: python generate_data.py
Writes 25 incidents to data/incidents/ and 10 runbooks to data/runbooks/
"""

import json
import os


INCIDENTS = [
    {
        "incident_id": "INC-2024-0001",
        "title": "Payment API intermittent 504 timeouts",
        "service": "payment-service",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-01-08T14:23:00Z",
        "description": (
            "Users reporting intermittent 504 Gateway Timeout on POST /v1/payments/charge. "
            "Started around 14:15 UTC. Approximately 30% of requests failing. "
            "Payment-service CPU and memory normal. No recent deploys in payment-service."
        ),
        "symptoms": [
            "504 Gateway Timeout on /v1/payments/charge",
            "Elevated DB connection pool wait time (avg 4.2s, normal <50ms)",
            "pg_stat_activity showing 80+ idle-in-transaction connections",
            "payment-service CPU normal at 18%",
        ],
        "root_cause": (
            "PostgreSQL connection pool exhausted. A bad query introduced in deploy INC-2024-0410 "
            "was holding transactions open for 30s+, starving the pool (max_connections=100)."
        ),
        "resolution": (
            "1. Rolled back deploy deploy-2024-0410. "
            "2. Killed idle-in-transaction connections older than 10s. "
            "3. Set statement_timeout=5000 in payment-service DB config. "
            "4. Ran VACUUM ANALYZE on payments table."
        ),
        "resolution_time_minutes": 47,
        "tags": ["database", "connection-pool", "postgres", "timeout", "payment"],
        "related_runbook": "RB-DB-001",
    },
    {
        "incident_id": "INC-2024-0002",
        "title": "Redis OOM causing cache stampede on product catalog",
        "service": "catalog-service",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-01-15T09:45:00Z",
        "description": (
            "Catalog service latency spiked from 45ms to 8s. Redis maxmemory-policy=allkeys-lru "
            "triggered mass eviction. All catalog requests hitting database simultaneously."
        ),
        "symptoms": [
            "catalog-service p99 latency: 8200ms (normal: 45ms)",
            "Redis used_memory at 99.8% of maxmemory (8GB)",
            "Redis keyspace_hits dropped 94%, keyspace_misses spiked",
            "MySQL slow query log flooded with catalog SELECTs",
            "Error rate 22% on GET /v1/products",
        ],
        "root_cause": (
            "Redis OOM eviction cleared all catalog cache keys. "
            "Thundering herd: all replicas queried MySQL simultaneously on cache miss. "
            "Root cause of OOM was a new feature storing large session blobs (avg 120KB each)."
        ),
        "resolution": (
            "1. Increased Redis maxmemory to 12GB. "
            "2. Added cache-aside with probabilistic early rehydration (jitter). "
            "3. Set TTL on session blobs to 15min, reduced size by compressing with zlib. "
            "4. Added Redis memory alert at 75% threshold."
        ),
        "resolution_time_minutes": 62,
        "tags": ["redis", "cache", "oom", "stampede", "catalog", "latency"],
        "related_runbook": "RB-REDIS-001",
    },
    {
        "incident_id": "INC-2024-0003",
        "title": "Stripe webhook processing lag — orders stuck in pending",
        "service": "order-service",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-01-22T16:10:00Z",
        "description": (
            "Orders stuck in 'payment_pending' state. Stripe dashboard shows webhooks delivering "
            "successfully (HTTP 200 from our endpoint) but order state not updating. "
            "Customer support seeing surge of 'order not confirmed' tickets."
        ),
        "symptoms": [
            "Webhook endpoint returning 200 but not processing events",
            "order_events Kafka topic consumer lag: 142,000 messages",
            "order-processor pod OOMKilled 3 times in last hour",
            "Orders in payment_pending > 15min: 847",
        ],
        "root_cause": (
            "order-processor pod hitting 512MB memory limit and OOMKilling mid-processing. "
            "Kafka consumer not committing offset on crash, causing reprocessing loop. "
            "Memory leak introduced in v2.3.1: payment event objects not released after processing."
        ),
        "resolution": (
            "1. Increased order-processor memory limit to 1GB. "
            "2. Deployed hotfix v2.3.2 with memory leak fix. "
            "3. Manually reset Kafka consumer group offset to earliest unprocessed. "
            "4. Backfilled 847 stuck orders by replaying events."
        ),
        "resolution_time_minutes": 95,
        "tags": ["kafka", "oom", "memory-leak", "webhook", "orders", "kubernetes"],
        "related_runbook": "RB-KAFKA-001",
    },
    {
        "incident_id": "INC-2024-0004",
        "title": "Auth service returning 401 for valid tokens after key rotation",
        "service": "auth-service",
        "severity": "P1",
        "environment": "production",
        "timestamp": "2024-02-01T11:30:00Z",
        "description": (
            "All authenticated API requests returning 401 Unauthorized. "
            "Started immediately after planned JWT signing key rotation at 11:28 UTC. "
            "Users cannot log in. All services behind API gateway affected."
        ),
        "symptoms": [
            "100% 401 error rate across all authenticated endpoints",
            "auth-service logs: 'signature verification failed' for all tokens",
            "Key rotation completed at 11:28 UTC (2 min before incident)",
            "auth-service jwks endpoint returning new public key",
            "API gateway not yet serving updated JWKS",
        ],
        "root_cause": (
            "JWT signing key rotated in auth-service but API gateway cached the old JWKS "
            "with a 1-hour TTL. Gateway validating tokens with stale public key. "
            "Key rotation runbook did not include gateway JWKS cache invalidation step."
        ),
        "resolution": (
            "1. Manually invalidated JWKS cache on all API gateway instances. "
            "2. Issued emergency re-login tokens for active sessions. "
            "3. Updated key rotation runbook with cache invalidation step. "
            "4. Reduced JWKS TTL from 1h to 5min."
        ),
        "resolution_time_minutes": 18,
        "tags": ["auth", "jwt", "key-rotation", "cache", "api-gateway", "p1"],
        "related_runbook": "RB-AUTH-001",
    },
    {
        "incident_id": "INC-2024-0005",
        "title": "Node.js notification service OOM kills — memory leak",
        "service": "notification-service",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-02-08T03:20:00Z",
        "description": (
            "notification-service pods cycling every 4-6 hours with OOMKill. "
            "Email and push notifications delayed up to 3 hours. "
            "Memory usage grows linearly from restart, no plateau."
        ),
        "symptoms": [
            "Pod memory growing ~50MB/hour from baseline of 200MB",
            "OOMKill at 512MB limit every ~5-6 hours",
            "Node.js heap snapshot shows EventEmitter listeners not removed",
            "Email queue depth growing: 12,000 pending at time of report",
            "No memory growth in staging — only production",
        ],
        "root_cause": (
            "EventEmitter listeners added on each inbound webhook but never removed after processing. "
            "Production has 50x more events than staging so leak only manifests under load. "
            "Introduced in v1.8.0 refactor of webhook handler."
        ),
        "resolution": (
            "1. Deployed v1.8.1 with listener cleanup in webhook handler finally block. "
            "2. Increased memory limit to 1GB temporarily during fix deployment. "
            "3. Drained email queue by spinning up 3 extra replicas. "
            "4. Added heap memory alert at 400MB."
        ),
        "resolution_time_minutes": 210,
        "tags": [
            "nodejs",
            "memory-leak",
            "oom",
            "eventemitter",
            "notifications",
            "kubernetes",
        ],
        "related_runbook": "RB-K8S-001",
    },
    {
        "incident_id": "INC-2024-0006",
        "title": "DNS resolution failures causing inter-service timeouts",
        "service": "api-gateway",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-02-14T08:05:00Z",
        "description": (
            "api-gateway failing to resolve internal service hostnames intermittently. "
            "30-40% of requests to downstream services timing out with connection refused. "
            "Issue is intermittent — resolves and recurs every few minutes."
        ),
        "symptoms": [
            "NXDOMAIN errors in api-gateway logs for internal hostnames",
            "kube-dns pod CPU at 98%, request queue backing up",
            "ndots:5 in pod resolv.conf causing 5 DNS lookups per request",
            "api-gateway retry exhaustion logs",
        ],
        "root_cause": (
            "kube-dns overwhelmed by excessive DNS lookups. "
            "ndots:5 setting causes each lookup to attempt 5 search domain variations. "
            "New high-traffic service deployed with no DNS caching, generating 500k DNS req/min."
        ),
        "resolution": (
            "1. Set ndots:1 in new service pod spec. "
            "2. Added dnsCacheTTL: 30 to CoreDNS config. "
            "3. Scaled kube-dns from 2 to 4 replicas. "
            "4. Added NodeLocal DNSCache daemonset."
        ),
        "resolution_time_minutes": 35,
        "tags": ["dns", "kubernetes", "coredns", "networking", "timeout"],
        "related_runbook": "RB-K8S-001",
    },
    {
        "incident_id": "INC-2024-0007",
        "title": "SSL certificate expiry causing HTTPS failures on checkout",
        "service": "checkout-service",
        "severity": "P1",
        "environment": "production",
        "timestamp": "2024-02-20T00:01:00Z",
        "description": (
            "checkout.example.com returning SSL_ERROR_RX_RECORD_TOO_LONG at midnight. "
            "TLS certificate expired at 00:00 UTC. Checkout completely unavailable. "
            "cert-manager auto-renewal failed silently 72 hours earlier."
        ),
        "symptoms": [
            "SSL handshake failing for checkout.example.com",
            "Certificate expiry: 2024-02-20T00:00:00Z (just expired)",
            "cert-manager CertificateRequest status: Failed (72h ago)",
            "Let's Encrypt rate limit hit — 5 failed attempts in last 72h",
            "100% checkout failure rate",
        ],
        "root_cause": (
            "cert-manager CertificateRequest failed due to Let's Encrypt rate limiting. "
            "Root cause: cert-manager configured to renew at 30d before expiry, "
            "but Let's Encrypt was rate-limited due to 4 failed renewals from misconfigured ACME solver. "
            "No alerting on CertificateRequest failures."
        ),
        "resolution": (
            "1. Immediately deployed pre-provisioned wildcard cert from AWS ACM as emergency. "
            "2. Fixed ACME HTTP-01 solver ingress path (was missing /.well-known prefix). "
            "3. Issued new cert successfully. "
            "4. Added PagerDuty alert for CertificateRequest failures and cert expiry <14d."
        ),
        "resolution_time_minutes": 28,
        "tags": [
            "ssl",
            "tls",
            "certificate",
            "cert-manager",
            "lets-encrypt",
            "checkout",
            "p1",
        ],
        "related_runbook": "RB-SSL-001",
    },
    {
        "incident_id": "INC-2024-0008",
        "title": "Kafka consumer group rebalancing storm — search indexing stalled",
        "service": "search-indexer",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-02-27T10:15:00Z",
        "description": (
            "Search index falling behind real-time by 45+ minutes. "
            "search-indexer consumer group in constant rebalancing. "
            "Product updates not appearing in search results."
        ),
        "symptoms": [
            "Kafka consumer group 'search-indexer' rebalancing every 30s",
            "search-index lag: 890,000 messages",
            "Consumer logs: 'Heartbeat timeout, rebalancing triggered'",
            "search-indexer processing time per batch: 28s (session.timeout.ms=10s)",
            "Product search stale by 48 minutes",
        ],
        "root_cause": (
            "search-indexer batch processing time (28s) exceeded Kafka session.timeout.ms (10s). "
            "Each timeout triggers a full consumer group rebalance. "
            "Batch size increased from 100 to 500 records in last deploy without adjusting timeouts."
        ),
        "resolution": (
            "1. Set session.timeout.ms=60000 and max.poll.interval.ms=120000. "
            "2. Reverted batch size to 100 records. "
            "3. Consumer group caught up over 90 minutes. "
            "4. Added consumer lag alert at >50k messages."
        ),
        "resolution_time_minutes": 130,
        "tags": [
            "kafka",
            "consumer-group",
            "rebalancing",
            "search",
            "indexing",
            "timeout",
        ],
        "related_runbook": "RB-KAFKA-001",
    },
    {
        "incident_id": "INC-2024-0009",
        "title": "Misconfigured ALB health check causing rolling pod restarts",
        "service": "user-service",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-03-05T13:40:00Z",
        "description": (
            "user-service pods cycling in rolling restarts every 2-3 minutes. "
            "5xx errors on all user-service endpoints. New deploy just completed. "
            "ALB target group showing all targets unhealthy."
        ),
        "symptoms": [
            "ALB target group: 0/8 targets healthy",
            "user-service pods in CrashLoopBackOff after 2-3 min",
            "ALB health check path: /health — returning 404",
            "user-service actual health endpoint: /api/health",
            "Deploy completed 8 minutes before incident",
        ],
        "root_cause": (
            "New deploy changed health check path from /health to /api/health "
            "but ALB target group health check was not updated. "
            "ALB marking all pods unhealthy, triggering liveness probe failures, "
            "which causes Kubernetes to restart pods in a loop."
        ),
        "resolution": (
            "1. Updated ALB target group health check path to /api/health. "
            "2. Targets became healthy within 90 seconds. "
            "3. Added health check path to deployment checklist. "
            "4. Standardized health endpoint path across all services to /health."
        ),
        "resolution_time_minutes": 22,
        "tags": ["alb", "health-check", "kubernetes", "load-balancer", "deploy", "5xx"],
        "related_runbook": "RB-K8S-001",
    },
    {
        "incident_id": "INC-2024-0010",
        "title": "MySQL replication lag causing stale reads in reporting service",
        "service": "reporting-service",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-03-12T09:00:00Z",
        "description": (
            "Reporting dashboard showing data from 4-6 hours ago. "
            "Users reporting revenue numbers not matching. "
            "reporting-service reads from MySQL read replica."
        ),
        "symptoms": [
            "MySQL replica Seconds_Behind_Master: 18,400 seconds",
            "Replica I/O thread: running, SQL thread: running",
            "Large batch job ran on primary at 03:00 UTC (INSERT 4.2M rows)",
            "Replica disk I/O at 100% saturation",
            "Reporting dashboard lag: ~5 hours",
        ],
        "root_cause": (
            "Overnight batch job inserted 4.2M rows into orders_archive in a single transaction. "
            "Replica applying binlog sequentially, disk I/O saturated. "
            "Replica using magnetic HDD, primary on SSD — I/O throughput mismatch."
        ),
        "resolution": (
            "1. Switched reporting-service to read from primary temporarily. "
            "2. Let replica catch up over 6 hours (no intervention needed). "
            "3. Migrated replica to SSD-backed storage. "
            "4. Rewrote batch job to batch 10k rows with 100ms sleep between batches."
        ),
        "resolution_time_minutes": 360,
        "tags": ["mysql", "replication", "lag", "replica", "batch-job", "reporting"],
        "related_runbook": "RB-DB-001",
    },
    {
        "incident_id": "INC-2024-0011",
        "title": "S3 presigned URL expiry causing image upload failures",
        "service": "media-service",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-03-18T15:30:00Z",
        "description": (
            "Users unable to upload profile images and product photos. "
            "media-service generates S3 presigned URLs — clients using URL 15+ minutes after generation. "
            "Upload success rate dropped from 99.8% to 31%."
        ),
        "symptoms": [
            "S3 upload error: 403 Request has expired",
            "presigned URL TTL: 900 seconds (15 min) — unchanged",
            "Mobile app v4.2.0 introduced async upload queue — delays upload by 5-30min",
            "Upload failure rate: 69%",
        ],
        "root_cause": (
            "Mobile app v4.2.0 introduced background upload queue. "
            "URLs generated immediately but uploads happen when connectivity allows — often 20-40min later. "
            "Presigned URL TTL of 15min insufficient for async upload pattern."
        ),
        "resolution": (
            "1. Increased presigned URL TTL to 4 hours. "
            "2. Added URL expiry time in API response so mobile can detect and refresh. "
            "3. Added URL refresh endpoint for mobile to call before expiry. "
            "4. Added upload success rate alert at <95%."
        ),
        "resolution_time_minutes": 45,
        "tags": ["s3", "presigned-url", "upload", "mobile", "media", "403"],
        "related_runbook": "RB-AWS-001",
    },
    {
        "incident_id": "INC-2024-0012",
        "title": "Elasticsearch index mapping conflict causing 400 errors on log ingestion",
        "service": "logging-pipeline",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-03-25T11:00:00Z",
        "description": (
            "Centralized logging pipeline dropping 40% of log events. "
            "Elasticsearch returning 400 mapper_parsing_exception. "
            "Field 'duration' being sent as string in some services, integer in others."
        ),
        "symptoms": [
            "Elasticsearch ingest error: mapper_parsing_exception on field 'duration'",
            "40% of log events rejected",
            "Field 'duration': mapped as long, but auth-service sending '245ms' (string)",
            "Log gap in Kibana for auth-service logs",
        ],
        "root_cause": (
            "auth-service v3.1 changed 'duration' log field from integer milliseconds to human-readable string. "
            "Elasticsearch dynamic mapping had already inferred 'duration' as long. "
            "No schema validation in logging pipeline before ES ingest."
        ),
        "resolution": (
            "1. Reverted auth-service logging format to integer milliseconds. "
            "2. Added field type validation in Logstash pipeline. "
            "3. Created Elasticsearch index template enforcing field types. "
            "4. Replayed 4h of dropped logs from Kafka DLQ."
        ),
        "resolution_time_minutes": 80,
        "tags": ["elasticsearch", "mapping", "logging", "schema", "kafka", "dlq"],
        "related_runbook": "RB-KAFKA-001",
    },
    {
        "incident_id": "INC-2024-0013",
        "title": "Rate limiting misconfiguration causing API partner lockout",
        "service": "api-gateway",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-04-02T14:00:00Z",
        "description": (
            "Major API partner reporting all their API calls rejected with 429 Too Many Requests. "
            "Partner's rate limit tier is 10k req/min but gateway enforcing 100 req/min. "
            "Config change deployed this morning."
        ),
        "symptoms": [
            "Partner API key receiving 429 on all requests",
            "Rate limit header: X-RateLimit-Limit: 100 (should be 10000)",
            "Config deploy at 09:15 UTC — 5h before incident report",
            "Other partners unaffected",
            "Partner revenue impact: $45k/hour",
        ],
        "root_cause": (
            "Rate limit config YAML used partner ID as key. "
            "Deploy script sorted keys alphabetically, causing partner tier mapping to shift. "
            "Partner 'acme-corp' was assigned tier of 'acme-analytics' (next alphabetically, 100 req/min)."
        ),
        "resolution": (
            "1. Reverted rate limit config to previous version. "
            "2. Applied hotfix mapping partner IDs explicitly, not positionally. "
            "3. Refunded partner for downtime window. "
            "4. Added integration test verifying rate limits per partner after config deploy."
        ),
        "resolution_time_minutes": 25,
        "tags": ["rate-limiting", "api-gateway", "configuration", "partner", "429"],
        "related_runbook": "RB-AUTH-001",
    },
    {
        "incident_id": "INC-2024-0014",
        "title": "Disk space exhaustion on primary database server",
        "service": "database-primary",
        "severity": "P1",
        "environment": "production",
        "timestamp": "2024-04-10T02:15:00Z",
        "description": (
            "PostgreSQL primary went read-only at 02:15 UTC. "
            "All write operations failing. Disk usage at 100% on /var/lib/postgresql. "
            "No disk usage alert fired."
        ),
        "symptoms": [
            "PostgreSQL error: could not write to file — No space left on device",
            "Disk usage: 100% on /var/lib/postgresql (500GB volume)",
            "pg_wal directory: 48GB (normal: 2-4GB)",
            "pg_stat_replication: replica slot 'reporting-replica' inactive for 18 days",
            "Write failure rate: 100%",
        ],
        "root_cause": (
            "Inactive replication slot 'reporting-replica' prevented WAL cleanup. "
            "PostgreSQL retains WAL files until all replication slots have consumed them. "
            "Reporting replica was decommissioned 18 days ago but slot was not dropped. "
            "WAL accumulated at ~2.6GB/day over 18 days."
        ),
        "resolution": (
            "1. Dropped inactive replication slot: SELECT pg_drop_replication_slot('reporting-replica'). "
            "2. PostgreSQL immediately cleaned WAL, freeing 44GB. "
            "3. Database returned to read-write mode automatically. "
            "4. Added alert: disk >70%, WAL size >10GB, inactive replication slots."
        ),
        "resolution_time_minutes": 12,
        "tags": ["postgres", "disk-full", "wal", "replication-slot", "database", "p1"],
        "related_runbook": "RB-DB-001",
    },
    {
        "incident_id": "INC-2024-0015",
        "title": "CDN cache poisoning causing wrong user data served",
        "service": "cdn",
        "severity": "P1",
        "environment": "production",
        "timestamp": "2024-04-15T16:45:00Z",
        "description": (
            "Users seeing other users' account data on GET /v1/user/profile. "
            "CDN caching personalized responses that should not be cached. "
            "New CDN config deployed at 16:30 UTC."
        ),
        "symptoms": [
            "Users seeing wrong profile data (other users' names, emails)",
            "CDN cache hit rate: 78% on /v1/user/profile (should be 0%)",
            "Response headers missing Cache-Control: no-store",
            "CDN config deploy at 16:30 UTC",
            "GDPR data breach potential",
        ],
        "root_cause": (
            "CDN config deploy accidentally removed Cache-Control header passthrough rule. "
            "CDN defaulted to caching all responses. "
            "/v1/user/profile returns user-specific data but CDN caching by URL only, "
            "not by auth token."
        ),
        "resolution": (
            "1. Immediately purged entire CDN cache. "
            "2. Reverted CDN config to previous version. "
            "3. Added Cache-Control: no-store to all /v1/user/* endpoints at origin. "
            "4. Filed GDPR incident report. "
            "5. Notified affected users."
        ),
        "resolution_time_minutes": 14,
        "tags": ["cdn", "cache", "privacy", "gdpr", "configuration", "p1"],
        "related_runbook": "RB-AWS-001",
    },
    {
        "incident_id": "INC-2024-0016",
        "title": "gRPC connection pool exhaustion between microservices",
        "service": "inventory-service",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-04-22T10:30:00Z",
        "description": (
            "inventory-service failing to call warehouse-service via gRPC. "
            "Error: 'no free connections in pool'. "
            "Order fulfillment blocked. Started after traffic spike from flash sale."
        ),
        "symptoms": [
            "gRPC error: RESOURCE_EXHAUSTED — no free connections in pool",
            "inventory→warehouse gRPC pool: 10 connections (pool max: 10)",
            "warehouse-service gRPC handler avg response time: 2.1s (normal: 80ms)",
            "Flash sale started 10:00 UTC — 8x normal traffic",
            "inventory-service request queue depth: 4,200",
        ],
        "root_cause": (
            "gRPC connection pool max set to 10 (hardcoded). "
            "warehouse-service slow due to DB query missing index on product_sku column. "
            "Slow responses held connections longer, exhausting pool under flash sale load."
        ),
        "resolution": (
            "1. Added index on warehouse.products(product_sku). "
            "2. Warehouse response time dropped to 45ms. Pool pressure relieved. "
            "3. Increased gRPC pool max to 50 (config, not hardcode). "
            "4. Added gRPC pool utilization alert at 80%."
        ),
        "resolution_time_minutes": 40,
        "tags": [
            "grpc",
            "connection-pool",
            "database",
            "index",
            "inventory",
            "performance",
        ],
        "related_runbook": "RB-DB-001",
    },
    {
        "incident_id": "INC-2024-0017",
        "title": "CircuitBreaker open state cascading failure across services",
        "service": "recommendation-service",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-05-01T18:00:00Z",
        "description": (
            "recommendation-service circuit breaker opened against product-service. "
            "Fallback serving empty recommendations. "
            "Homepage conversion rate dropped 18%."
        ),
        "symptoms": [
            "CircuitBreaker state: OPEN for recommendation→product-service",
            "product-service health: degraded (p99: 12s, normal: 200ms)",
            "recommendation-service fallback: empty list returned",
            "Homepage add-to-cart rate: -18%",
            "product-service DB read replica: Seconds_Behind_Master: 9000",
        ],
        "root_cause": (
            "product-service degraded due to read replica 150 min behind primary. "
            "All product reads routing to primary, overwhelming it. "
            "recommendation-service circuit breaker correctly opened to protect itself. "
            "Root cause: replica I/O thread stopped after network partition (recovered automatically but lag remained)."
        ),
        "resolution": (
            "1. Restarted MySQL replication: STOP SLAVE; START SLAVE;. "
            "2. Replica caught up in 45 minutes. "
            "3. product-service latency normalized. "
            "4. Circuit breaker auto-reset after half-open probe succeeded. "
            "5. Added replica lag alert at >300 seconds."
        ),
        "resolution_time_minutes": 75,
        "tags": [
            "circuit-breaker",
            "mysql",
            "replication",
            "cascade",
            "recommendation",
            "resilience",
        ],
        "related_runbook": "RB-DB-001",
    },
    {
        "incident_id": "INC-2024-0018",
        "title": "Terraform state lock preventing infrastructure changes",
        "service": "infrastructure",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-05-08T14:20:00Z",
        "description": (
            "All Terraform operations failing with state lock error. "
            "Infrastructure team unable to deploy fixes for other incidents. "
            "Lock held by a Terraform run that was forcibly killed 6 hours ago."
        ),
        "symptoms": [
            "Error: Error acquiring the state lock",
            "Lock holder: CI run #4892 (killed at 08:15 UTC)",
            "DynamoDB terraform-state-lock table: lock entry exists for workspace 'production'",
            "All infrastructure Terraform operations blocked",
            "6 hours since lock was orphaned",
        ],
        "root_cause": (
            "CI pipeline run killed mid-apply due to runner timeout. "
            "Terraform did not release DynamoDB state lock on forced termination. "
            "No automatic lock expiry configured."
        ),
        "resolution": (
            "1. Verified no Terraform apply was actively running. "
            "2. Ran: terraform force-unlock <lock-id>. "
            "3. Verified state file integrity with terraform plan. "
            "4. Set DynamoDB lock TTL to 2 hours via DynamoDB TTL attribute."
        ),
        "resolution_time_minutes": 15,
        "tags": ["terraform", "state-lock", "dynamodb", "infrastructure", "ci"],
        "related_runbook": "RB-AWS-001",
    },
    {
        "incident_id": "INC-2024-0019",
        "title": "Prometheus scrape timeout causing alert rule evaluation failures",
        "service": "monitoring",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-05-14T09:45:00Z",
        "description": (
            "Prometheus alert rules not firing despite known issues. "
            "PagerDuty silent for 2 hours. "
            "Prometheus scrape errors for 14 targets including payment-service."
        ),
        "symptoms": [
            "Prometheus scrape_duration_seconds > 10s for 14 targets",
            "Prometheus error: context deadline exceeded (scrape timeout 10s)",
            "payment-service /metrics endpoint response time: 45s",
            "Alert evaluation errors in Prometheus logs",
            "2 hours of missing metrics data",
        ],
        "root_cause": (
            "payment-service /metrics endpoint blocked by DB query during metrics collection. "
            "Metrics endpoint calling slow analytics query on each scrape. "
            "Scrape timeout (10s) exceeded, causing Prometheus to mark target as down. "
            "Alert rules dependent on payment-service metrics unable to evaluate."
        ),
        "resolution": (
            "1. Cached expensive metrics computation with 30s TTL in payment-service. "
            "2. /metrics endpoint response time dropped to <100ms. "
            "3. Prometheus scrape errors cleared. "
            "4. Replayed 2h of alerting rules against stored TSDB data. "
            "5. Added scrape error alert: >5% targets failing."
        ),
        "resolution_time_minutes": 50,
        "tags": [
            "prometheus",
            "monitoring",
            "metrics",
            "scrape",
            "alerting",
            "observability",
        ],
        "related_runbook": "RB-DB-001",
    },
    {
        "incident_id": "INC-2024-0020",
        "title": "Python service hitting open file descriptor limit",
        "service": "data-pipeline",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-05-20T22:10:00Z",
        "description": (
            "data-pipeline service crashing with 'Too many open files'. "
            "ETL jobs failing. "
            "File handle leak — each file processed opens an S3 connection not closed."
        ),
        "symptoms": [
            "OSError: [Errno 24] Too many open files",
            "ulimit -n: 1024 (system default)",
            "lsof | wc -l: 1,019 open file descriptors",
            "S3 boto3 client created per file, not reused",
            "Memory stable — not a memory leak",
        ],
        "root_cause": (
            "data-pipeline creating a new boto3 S3 client per file processed. "
            "Each client opens a persistent HTTP connection that is not closed explicitly. "
            "Under high throughput (500+ files/hour), descriptors exhausted in ~2 hours."
        ),
        "resolution": (
            "1. Refactored to singleton boto3 client with connection pooling. "
            "2. Increased ulimit to 65536 as safety margin: ulimit -n 65536. "
            "3. Added fd count monitoring: alert at >80% of ulimit. "
            "4. Added explicit client.close() in finally blocks."
        ),
        "resolution_time_minutes": 55,
        "tags": ["python", "file-descriptor", "s3", "boto3", "resource-leak", "etl"],
        "related_runbook": "RB-AWS-001",
    },
    {
        "incident_id": "INC-2024-0021",
        "title": "Kubernetes HPA scaling too slowly during traffic spike",
        "service": "api-gateway",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-05-27T12:00:00Z",
        "description": (
            "Product launch caused 10x traffic spike. "
            "api-gateway pods overwhelmed, p99 latency hit 18s. "
            "HPA scaled from 5 to 50 pods but took 12 minutes, too slow."
        ),
        "symptoms": [
            "api-gateway CPU: 98% across all 5 pods",
            "HPA: desired=50, current=5, scaling rate 1 pod/30s (default)",
            "p99 latency: 18,200ms for 12 minutes",
            "HPA scaleUp stabilization window: 5 minutes (default)",
            "New pod ready time: ~45s (slow image pull)",
        ],
        "root_cause": (
            "HPA default scaleUp behavior limited to 1 pod per 15s. "
            "Pod startup took 45s due to large Docker image (2.1GB) not pre-pulled on nodes. "
            "Combination of slow HPA scaling + slow pod startup meant 12min to reach capacity."
        ),
        "resolution": (
            "1. Set HPA scaleUp.policies: [{type: Pods, value: 10, periodSeconds: 60}]. "
            "2. Added node pre-pulling for api-gateway image via DaemonSet. "
            "3. Reduced image from 2.1GB to 340MB by switching to distroless base. "
            "4. Added pre-scaling automation triggered by marketing calendar events."
        ),
        "resolution_time_minutes": 15,
        "tags": [
            "kubernetes",
            "hpa",
            "autoscaling",
            "traffic-spike",
            "performance",
            "docker",
        ],
        "related_runbook": "RB-K8S-001",
    },
    {
        "incident_id": "INC-2024-0022",
        "title": "Dead letter queue accumulation — failed payment events unprocessed",
        "service": "payment-processor",
        "severity": "P2",
        "environment": "production",
        "timestamp": "2024-06-03T08:30:00Z",
        "description": (
            "payment-processor DLQ (SQS) accumulating failed events. "
            "2,400 failed payment events not processed. "
            "Deserialization error in new message format."
        ),
        "symptoms": [
            "SQS DLQ depth: 2,400 messages (growing)",
            "payment-processor error: JSONDecodeError — unexpected field 'payment_method_v2'",
            "New event schema deployed to payment-service at 06:00 UTC",
            "payment-processor not yet updated to new schema",
            "Failed events: all from 06:00–08:30 UTC window",
        ],
        "root_cause": (
            "payment-service deployed new event schema with additive field 'payment_method_v2'. "
            "payment-processor using strict Pydantic model — extra fields raise ValidationError. "
            "Schema change deployed without coordinated consumer update. "
            "No backward compatibility check in CI."
        ),
        "resolution": (
            "1. Deployed payment-processor with model_config = ConfigDict(extra='ignore'). "
            "2. Replayed 2,400 DLQ messages via SQS DLQ redrive. "
            "3. All messages processed successfully. "
            "4. Added schema compatibility check to CI pipeline."
        ),
        "resolution_time_minutes": 65,
        "tags": [
            "sqs",
            "dlq",
            "schema",
            "pydantic",
            "payment",
            "event-driven",
            "backward-compatibility",
        ],
        "related_runbook": "RB-KAFKA-001",
    },
    {
        "incident_id": "INC-2024-0023",
        "title": "Nginx upstream keepalive misconfiguration causing connection reset",
        "service": "nginx",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-06-10T14:05:00Z",
        "description": (
            "Intermittent 502 Bad Gateway errors from nginx. "
            "Approximately 5% of requests failing. "
            "Upstream services healthy. Only happens on requests with large response bodies."
        ),
        "symptoms": [
            "nginx error log: upstream prematurely closed connection",
            "5% 502 error rate",
            "Errors only on responses >1MB",
            "Upstream keepalive_timeout: 15s",
            "nginx proxy_read_timeout: 10s (lower than upstream keepalive)",
        ],
        "root_cause": (
            "nginx proxy_read_timeout (10s) shorter than upstream keepalive_timeout (15s). "
            "For large responses taking >10s to transfer, nginx closes the connection. "
            "Upstream interprets this as connection reset and logs error. "
            "Manifests only on large payloads (product export, report downloads)."
        ),
        "resolution": (
            "1. Set nginx proxy_read_timeout to 60s for /v1/exports/* location block. "
            "2. Set proxy_send_timeout to 60s. "
            "3. Added streaming for large export responses to avoid timeout entirely. "
            "4. Added 502 rate alert at >1%."
        ),
        "resolution_time_minutes": 30,
        "tags": ["nginx", "502", "timeout", "keepalive", "proxy", "configuration"],
        "related_runbook": "RB-K8S-001",
    },
    {
        "incident_id": "INC-2024-0024",
        "title": "AWS IAM permission boundary blocking Lambda execution",
        "service": "lambda-image-processor",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-06-17T10:20:00Z",
        "description": (
            "Image processing Lambda failing to write processed images to S3. "
            "Lambda execution role has s3:PutObject in IAM policy "
            "but still getting AccessDenied. Recently applied permission boundary."
        ),
        "symptoms": [
            "Lambda error: AccessDenied on s3:PutObject to bucket img-processed-prod",
            "IAM policy attached: allows s3:PutObject on arn:aws:s3:::img-processed-prod/*",
            "Permission boundary applied yesterday: restricts to arn:aws:s3:::img-*-staging/*",
            "Lambda working in staging environment",
        ],
        "root_cause": (
            "IAM permission boundary applied to Lambda execution role restricts to staging S3 buckets only. "
            "Effective permissions = intersection(IAM policy, permission boundary). "
            "Policy allows prod bucket, boundary allows only staging — intersection is empty. "
            "Boundary was copied from staging environment without modification."
        ),
        "resolution": (
            "1. Updated permission boundary to include arn:aws:s3:::img-*-prod/*. "
            "2. Lambda immediately able to write to prod S3. "
            "3. Reprocessed 847 failed image jobs. "
            "4. Added boundary review step to IAM change process."
        ),
        "resolution_time_minutes": 35,
        "tags": ["aws", "iam", "lambda", "permission-boundary", "s3", "access-denied"],
        "related_runbook": "RB-AWS-001",
    },
    {
        "incident_id": "INC-2024-0025",
        "title": "Go service goroutine leak causing gradual memory growth",
        "service": "analytics-service",
        "severity": "P3",
        "environment": "production",
        "timestamp": "2024-06-24T06:00:00Z",
        "description": (
            "analytics-service memory growing 200MB/hour. "
            "Service restarts every 6-8 hours. "
            "pprof goroutine count growing linearly — not GC-related."
        ),
        "symptoms": [
            "Goroutine count: 12,400 (normal: 50-200)",
            "Memory: 4.1GB and growing (limit: 4GB)",
            "pprof heap: stable, goroutine: linear growth",
            "Goroutine stack trace: blocked on channel receive in event subscriber",
            "analytics-service event subscriber not cancelling context on timeout",
        ],
        "root_cause": (
            "Event subscriber spawning goroutine per event. "
            "Goroutines blocked waiting on channel that is closed only on successful processing. "
            "On timeout (context deadline), goroutine not signalled — leaks. "
            "Under normal load (100 events/min), leak rate too slow to notice. "
            "Recent 5x traffic increase made leak visible."
        ),
        "resolution": (
            "1. Fixed goroutine to select on ctx.Done() in addition to result channel. "
            "2. Deployed v2.1.1. "
            "3. Goroutine count dropped to 180 within 5 minutes. "
            "4. Added goroutine count alert at >1000. "
            "5. Added pprof endpoint to standard service template."
        ),
        "resolution_time_minutes": 45,
        "tags": [
            "golang",
            "goroutine-leak",
            "memory",
            "concurrency",
            "analytics",
            "pprof",
        ],
        "related_runbook": "RB-K8S-001",
    },
]

RUNBOOKS = {
    "RB-DB-001.md": """---
runbook_id: RB-DB-001
title: Database connection pool and replication issues
service: any
tags: [database, postgres, mysql, connection-pool, replication]
last_updated: 2024-01-01
---
 
## Overview
This runbook covers PostgreSQL and MySQL issues including connection pool exhaustion,
replication lag, disk space from WAL accumulation, and slow query diagnosis.
 
## Symptoms
- High DB wait time in APM (>500ms)
- 504/503 errors from DB-backed services
- pg_stat_activity showing many idle-in-transaction connections
- MySQL Seconds_Behind_Master > 60
- PostgreSQL read-only mode (disk full)
 
## Diagnostic steps
 
### Connection pool
```sql
-- Check active connections
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
 
-- Find long-running queries
SELECT pid, query, now() - query_start AS duration
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;
 
-- Kill a specific connection
SELECT pg_terminate_backend(<pid>);
```
 
### Replication lag (PostgreSQL)
```sql
-- Check replication slots
SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes
FROM pg_replication_slots;
 
-- Drop inactive slot
SELECT pg_drop_replication_slot('<slot_name>');
```
 
### Disk / WAL
```bash
# Check disk usage
df -h /var/lib/postgresql
 
# Check WAL directory size
du -sh /var/lib/postgresql/*/pg_wal
```
 
### MySQL replication
```sql
SHOW SLAVE STATUS\\G
-- Check Seconds_Behind_Master
 
-- Restart replication if needed
STOP SLAVE; START SLAVE;
```
 
## Fix: connection pool exhausted
1. Kill idle-in-transaction connections older than 30s
2. Set `statement_timeout` to limit runaway queries
3. Increase pool size in application config (restart required)
4. Identify and fix slow queries causing pool starvation
 
## Fix: WAL disk exhaustion
1. Identify inactive replication slots: `SELECT * FROM pg_replication_slots WHERE active = false;`
2. Drop the slot after confirming replica is decommissioned
3. PostgreSQL will auto-cleanup WAL files
 
## Prevention
- Alert: DB connections > 80% of max_connections
- Alert: Replication lag > 300 seconds
- Alert: Disk usage > 70%
- Alert: WAL directory > 10GB
- Alert: Inactive replication slots > 0
""",
    "RB-REDIS-001.md": """---
runbook_id: RB-REDIS-001
title: Redis OOM, eviction, and cache stampede
service: any
tags: [redis, cache, oom, stampede, eviction]
last_updated: 2024-01-15
---
 
## Overview
Covers Redis out-of-memory events, eviction-triggered cache stampedes,
and memory pressure diagnosis.
 
## Symptoms
- Redis used_memory at or near maxmemory
- Sudden drop in keyspace_hits, spike in keyspace_misses
- Downstream DB CPU spiking on cache miss
- Application latency spike from cache miss path
 
## Diagnostic steps
 
```bash
# Check memory
redis-cli INFO memory | grep -E 'used_memory_human|maxmemory_human|mem_fragmentation'
 
# Check eviction stats
redis-cli INFO stats | grep -E 'evicted_keys|keyspace_hits|keyspace_misses'
 
# Check key count and biggest keys
redis-cli DBSIZE
redis-cli --bigkeys
 
# Check maxmemory policy
redis-cli CONFIG GET maxmemory-policy
```
 
## Fix: OOM / eviction stampede
1. Immediately increase maxmemory (if headroom available on host):
   `redis-cli CONFIG SET maxmemory 12gb`
2. Identify and evict large unnecessary keys (--bigkeys output)
3. Implement probabilistic early rehydration to prevent future stampedes:
   - On cache hit, if TTL < threshold, proactively refresh in background
4. Add jitter to TTLs to prevent synchronized expiry
 
## Fix: large value OOM
1. Identify large key classes from --bigkeys
2. Compress large values (zlib, snappy) before storing
3. Reduce TTL on large ephemeral values
4. Consider storing large values in S3 with Redis holding only a pointer
 
## Prevention
- Alert: Redis memory > 75% of maxmemory
- Alert: evicted_keys growing rapidly (>1000/min)
- Alert: keyspace_miss_rate > 20% (sudden change from baseline)
- Set appropriate maxmemory-policy for your use case (allkeys-lru for cache, noeviction for session store)
""",
    "RB-KAFKA-001.md": """---
runbook_id: RB-KAFKA-001
title: Kafka consumer lag, rebalancing, and DLQ handling
service: any
tags: [kafka, consumer, lag, rebalancing, dlq, sqs]
last_updated: 2024-02-01
---
 
## Overview
Covers Kafka consumer group issues: lag accumulation, rebalancing storms,
offset management, and dead letter queue handling.
 
## Symptoms
- Consumer group lag growing
- Consumer group in constant rebalancing state
- Messages landing in DLQ
- Processing order not guaranteed
 
## Diagnostic steps
 
```bash
# Check consumer group lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \\
  --group <group-name> --describe
 
# Check consumer group state
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \\
  --group <group-name> --describe | grep State
 
# List all consumer groups
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list
```
 
## Fix: rebalancing storm
1. Increase `session.timeout.ms` to be greater than max processing time per batch
2. Increase `max.poll.interval.ms` to match expected processing time
3. Reduce batch size if processing time is too long
4. Add heartbeat thread separate from processing thread
 
Recommended settings for slow processors:
```properties
session.timeout.ms=60000
max.poll.interval.ms=300000
heartbeat.interval.ms=10000
```
 
## Fix: consumer lag catchup
1. Increase consumer replicas temporarily
2. Reduce processing complexity (skip enrichment, process raw events)
3. If lag is unrecoverable, reset offset to recent point:
```bash
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \\
  --group <group-name> --reset-offsets --to-latest --execute --topic <topic>
```
 
## Fix: DLQ message replay (SQS)
1. Go to SQS console → DLQ → Start DLQ redrive
2. Or use AWS CLI:
```bash
aws sqs start-message-move-task \\
  --source-queue-url <dlq-url> \\
  --destination-queue-url <source-queue-url>
```
3. Monitor processing — ensure root cause fixed before replay
 
## Prevention
- Alert: Consumer lag > 10,000 messages
- Alert: Consumer group state = Dead or Rebalancing for > 60s
- Alert: DLQ depth > 100
- Use idempotent consumers — replay safety is critical
""",
    "RB-AUTH-001.md": """---
runbook_id: RB-AUTH-001
title: Authentication failures — JWT, key rotation, rate limiting
service: auth-service, api-gateway
tags: [auth, jwt, key-rotation, rate-limiting, 401, 429]
last_updated: 2024-02-01
---
 
## Overview
Covers authentication service incidents: JWT validation failures after key rotation,
JWKS cache staleness, and rate limit misconfiguration.
 
## Symptoms
- 401 Unauthorized across all authenticated endpoints
- 429 Too Many Requests for specific API consumers
- auth-service logs: signature verification failed
- Sudden onset after config or key rotation event
 
## Diagnostic steps
 
### JWT validation failure
```bash
# Check current JWKS from auth service
curl https://auth.internal/jwks | jq .
 
# Check what key API gateway is using
curl https://api-gateway.internal/debug/jwks | jq .
 
# Decode JWT (without verification) to check kid
echo "<jwt>" | cut -d. -f2 | base64 -d | jq .
```
 
### Rate limiting
```bash
# Check rate limit headers on a request
curl -v -H "Authorization: Bearer <token>" https://api.example.com/v1/endpoint 2>&1 | grep -i ratelimit
 
# Check rate limit config
cat /etc/api-gateway/rate-limits.yaml
```
 
## Fix: JWKS cache stale after key rotation
1. Identify all services caching JWKS (API gateway, service mesh, etc.)
2. Force cache invalidation on each:
   - API gateway: `kubectl rollout restart deployment/api-gateway`
   - Or call cache-clear admin endpoint if available
3. Verify new JWKS is being served everywhere
4. Reduce JWKS TTL to 5 minutes for future rotations
 
## Fix: rate limit misconfiguration
1. Identify affected API key/consumer from 429 response headers
2. Check rate limit config: verify tier assignment for consumer
3. Apply correct tier immediately (hot reload if supported)
4. Audit other consumers for similar misconfiguration
 
## Key rotation checklist (run BEFORE rotating)
- [ ] Identify all JWKS consumers (services, gateways, edge functions)
- [ ] Reduce JWKS TTL to 1 minute, wait for TTL to expire everywhere
- [ ] Rotate key
- [ ] Verify new JWKS propagated to all consumers
- [ ] Restore JWKS TTL
 
## Prevention
- Alert: 401 error rate > 1% (sudden spike)
- Alert: 429 rate for any single consumer > 50% of their tier limit
- Test JWKS propagation in staging before production key rotation
""",
    "RB-K8S-001.md": """---
runbook_id: RB-K8S-001
title: Kubernetes pod issues — OOM, CrashLoopBackOff, HPA, DNS
service: any
tags: [kubernetes, oom, crashloop, hpa, dns, deployment]
last_updated: 2024-03-01
---
 
## Overview
Covers common Kubernetes operational issues: OOMKill, CrashLoopBackOff diagnosis,
HPA scaling configuration, DNS failures, and resource limits.
 
## Symptoms
- Pod in CrashLoopBackOff
- OOMKilled in pod events
- HPA not scaling fast enough
- DNS resolution failures (NXDOMAIN)
- Service endpoints not reachable after deploy
 
## Diagnostic steps
 
```bash
# Pod status
kubectl get pods -n <namespace> -o wide
 
# Pod events (why it crashed)
kubectl describe pod <pod-name> -n <namespace>
 
# Recent logs
kubectl logs <pod-name> -n <namespace> --previous
 
# Resource usage
kubectl top pods -n <namespace>
 
# HPA status
kubectl get hpa -n <namespace>
kubectl describe hpa <name> -n <namespace>
 
# DNS test
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup <service-name>
```
 
## Fix: OOMKill
1. Check memory usage trend: kubectl top pods
2. Increase memory limit: edit deployment → resources.limits.memory
3. Check for memory leak: heap dumps, goroutine count (Go), heap snapshot (Node.js)
4. Set alert at 80% of memory limit
 
## Fix: CrashLoopBackOff
1. Check exit code: `kubectl describe pod` → exit code 137 = OOM, 1 = app error, 139 = segfault
2. Check previous logs: `kubectl logs --previous`
3. Check liveness probe — may be too aggressive
4. Check health check endpoint path matches actual endpoint
 
## Fix: HPA scaling too slow
1. Increase scale-up rate:
```yaml
behavior:
  scaleUp:
    policies:
    - type: Pods
      value: 10
      periodSeconds: 60
```
2. Reduce pod startup time: use distroless images, pre-pull images with DaemonSet
3. For predictable spikes: pre-scale before the event
 
## Fix: DNS resolution failure
1. Check CoreDNS pods: `kubectl get pods -n kube-system | grep coredns`
2. Scale CoreDNS: `kubectl scale deployment coredns --replicas=4 -n kube-system`
3. Check ndots setting in pod: `cat /etc/resolv.conf`
4. Set `ndots: 1` in pod spec for services using fully-qualified names
 
## Prevention
- Alert: OOMKill events in last 30 minutes
- Alert: CrashLoopBackOff for > 5 minutes
- Alert: HPA at max replicas for > 10 minutes (can't scale further)
- Alert: CoreDNS error rate > 1%
""",
    "RB-SSL-001.md": """---
runbook_id: RB-SSL-001
title: SSL/TLS certificate expiry and renewal failures
service: any
tags: [ssl, tls, certificate, cert-manager, lets-encrypt]
last_updated: 2024-02-20
---
 
## Overview
Covers TLS certificate issues: expired certificates, cert-manager renewal failures,
Let's Encrypt rate limiting, and emergency certificate replacement.
 
## Symptoms
- SSL_ERROR_RX_RECORD_TOO_LONG or NET::ERR_CERT_DATE_INVALID in browsers
- cert-manager CertificateRequest in Failed state
- Let's Encrypt rate limit errors in cert-manager logs
 
## Diagnostic steps
 
```bash
# Check certificate expiry
echo | openssl s_client -connect <domain>:443 2>/dev/null | openssl x509 -noout -dates
 
# Check cert-manager Certificate objects
kubectl get certificate -A
kubectl describe certificate <name> -n <namespace>
 
# Check CertificateRequest status
kubectl get certificaterequest -A
kubectl describe certificaterequest <name> -n <namespace>
 
# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager | tail -100
```
 
## Fix: expired certificate (emergency)
Option A — Use pre-provisioned wildcard cert (fastest):
1. Deploy wildcard cert from AWS ACM, GCP Certificate Manager, or vault
2. Update Ingress/Gateway TLS secret
3. Traffic recovers immediately
 
Option B — Force cert-manager renewal:
1. Delete failed CertificateRequest: `kubectl delete certificaterequest <name>`
2. cert-manager will create a new one and retry
3. If Let's Encrypt rate limited, wait 1 hour or use staging ACME server
 
## Fix: ACME HTTP-01 challenge failing
1. Verify Ingress has route for `/.well-known/acme-challenge/*`
2. Verify challenge endpoint reachable from external internet
3. Check for WAF or CDN blocking the challenge path
 
## Fix: Let's Encrypt rate limit
- Rate limit: 5 failed validations per hostname per hour
- Wait 1 hour, then retry
- For immediate recovery: use paid cert from DigiCert/Sectigo
 
## Prevention
- Alert: Certificate expiry < 14 days
- Alert: CertificateRequest in Failed state for > 30 minutes
- Use wildcard certs for disaster recovery
- Test ACME renewal in staging monthly
""",
    "RB-AWS-001.md": """---
runbook_id: RB-AWS-001
title: AWS service issues — S3, IAM, Lambda, CDN, Terraform
service: infrastructure
tags: [aws, s3, iam, lambda, cloudfront, terraform, permissions]
last_updated: 2024-03-01
---
 
## Overview
Covers AWS-specific operational issues: S3 access errors, IAM permission problems
(including permission boundaries), CDN cache issues, Lambda failures, and
Terraform state lock issues.
 
## Symptoms
- S3: 403 AccessDenied or Request has expired
- IAM: AccessDenied despite policy allowing action
- Terraform: Error acquiring the state lock
- CDN: wrong content served, cache not invalidating
 
## Diagnostic steps
 
### S3 access
```bash
# Check who's calling and what error
aws s3 cp s3://<bucket>/<key> . --debug 2>&1 | grep -i 'access\|denied\|expired'
 
# Check presigned URL expiry
aws s3 presign s3://<bucket>/<key> --expires-in 3600
```
 
### IAM / permission boundary
```bash
# Simulate IAM policy evaluation
aws iam simulate-principal-policy \\
  --policy-source-arn arn:aws:iam::<account>:role/<role-name> \\
  --action-names s3:PutObject \\
  --resource-arns arn:aws:s3:::<bucket>/*
 
# Get attached permission boundary
aws iam get-role --role-name <role-name> | jq .Role.PermissionsBoundary
```
 
### Terraform state lock
```bash
# List locks in DynamoDB
aws dynamodb scan --table-name terraform-state-lock
 
# Force unlock (verify no apply is running first!)
terraform force-unlock <lock-id>
 
# Verify state integrity after unlock
terraform plan
```
 
### CloudFront cache
```bash
# Create invalidation
aws cloudfront create-invalidation \\
  --distribution-id <dist-id> \\
  --paths "/*"
 
# Check cache headers on response
curl -I https://<domain>/<path> | grep -i cache
```
 
## Fix: IAM permission boundary
Remember: effective permissions = intersection(identity policy, permission boundary).
Having s3:PutObject in the identity policy is NOT sufficient if the boundary doesn't include it.
 
1. Get current boundary ARN from role
2. View boundary policy document
3. Add missing action/resource to boundary
4. Or detach boundary if it was applied in error
 
## Fix: S3 presigned URL expired
1. Check TTL at generation time vs typical client usage time
2. Increase TTL if async usage pattern (e.g., mobile background uploads)
3. Add URL expiry time in API response so clients can detect and refresh
4. Add /refresh-upload-url endpoint
 
## Prevention
- Alert: S3 4xx error rate > 1%
- Alert: Lambda AccessDenied errors > 0
- Set DynamoDB TTL on Terraform lock table (2 hours)
- CDN: always verify Cache-Control headers after config deploy
""",
    "RB-PERF-001.md": """---
runbook_id: RB-PERF-001
title: Service latency and performance degradation
service: any
tags: [latency, performance, slow-query, profiling, index]
last_updated: 2024-04-01
---
 
## Overview
Covers latency spikes and performance degradation: slow DB queries, missing indexes,
connection pool saturation, and profiling approaches for Python, Go, and Node.js.
 
## Symptoms
- p99 latency spike (>2x normal)
- CPU spike on database server
- Slow query log volume increase
- APM showing specific endpoint degraded
 
## Diagnostic steps
 
### Database slow queries
```sql
-- PostgreSQL: recent slow queries
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
 
-- MySQL slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
 
-- Check missing indexes
EXPLAIN ANALYZE <your_slow_query>;
```
 
### Application profiling
```bash
# Python: py-spy (attach to running process)
py-spy top --pid <pid>
py-spy record -o profile.svg --pid <pid> --duration 30
 
# Go: pprof
curl http://localhost:6060/debug/pprof/goroutine?debug=1
go tool pprof http://localhost:6060/debug/pprof/heap
 
# Node.js: clinic.js
clinic doctor -- node server.js
```
 
## Fix: missing database index
1. Identify query from slow query log or EXPLAIN ANALYZE
2. Add index (use CONCURRENTLY in PostgreSQL to avoid table lock):
```sql
CREATE INDEX CONCURRENTLY idx_products_sku ON products(product_sku);
```
3. Verify query uses new index: `EXPLAIN ANALYZE <query>`
4. Monitor query execution time
 
## Fix: N+1 query pattern
1. Identify in APM: many small fast queries to same table
2. Replace with single query using IN() or JOIN
3. Add query result caching for read-heavy data
 
## Fix: connection pool saturation
See RB-DB-001 for connection pool exhaustion steps.
 
## Prevention
- Alert: p99 latency > 2x baseline (rolling 5min window)
- Alert: DB slow queries > 10/min
- Run EXPLAIN on all new queries in code review
- Load test before high-traffic events
""",
    "RB-OBSERVABILITY-001.md": """---
runbook_id: RB-OBSERVABILITY-001
title: Monitoring, alerting, and observability failures
service: monitoring
tags: [prometheus, alerting, metrics, logging, observability]
last_updated: 2024-05-01
---
 
## Overview
Covers monitoring stack issues: Prometheus scrape failures, alert rule evaluation errors,
log pipeline gaps, and metric collection problems.
 
## Symptoms
- Alerts not firing for known issues
- Metrics missing in dashboards
- Prometheus targets showing as Down
- Log gaps in Kibana/Grafana Loki
 
## Diagnostic steps
 
```bash
# Check Prometheus targets
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'
 
# Check scrape errors
curl http://prometheus:9090/api/v1/query?query=up | jq .
 
# Check alert rule evaluation
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[].rules[] | select(.health != "ok")'
 
# Test /metrics endpoint directly
curl http://<service>:<port>/metrics | head -50
 
# Check Prometheus config
kubectl exec -n monitoring deployment/prometheus -- cat /etc/prometheus/prometheus.yml
```
 
## Fix: scrape timeout
1. Check if /metrics endpoint is slow: `time curl http://<service>/metrics`
2. If slow: cache expensive metric computations in the service (30-60s TTL)
3. Increase scrape_timeout in Prometheus config (temporary mitigation)
4. Identify and fix slow metric computation
 
## Fix: alert not firing
1. Check if the alert rule is evaluating: `curl /api/v1/rules`
2. Check if dependent metrics are missing (scrape failure above)
3. Check alertmanager routing: `curl http://alertmanager:9093/api/v1/status`
4. Check alert inhibition rules — another alert may be silencing it
 
## Fix: log pipeline gap
1. Identify gap source: Logstash/Fluentd/Filebeat or Elasticsearch?
2. Check Kafka DLQ for dropped events (if using Kafka in pipeline)
3. Replay dropped events from DLQ or log archive (S3)
4. Check field type conflicts in Elasticsearch mappings
 
## Prevention
- Alert on alert: scrape_error_rate > 5% (meta-alerting)
- Alert: alertmanager_notifications_failed_total increasing
- Run monthly chaos test: deliberately cause an incident, verify alert fires
- Document expected alert→runbook mapping
""",
    "RB-SECURITY-001.md": """---
runbook_id: RB-SECURITY-001
title: Security incidents — data exposure, access control failures
service: any
tags: [security, privacy, gdpr, access-control, cdn, cache]
last_updated: 2024-04-15
---
 
## Overview
Covers security-related incidents: accidental data exposure via CDN/cache misconfiguration,
access control failures, and immediate response steps.
 
## Symptoms
- Users seeing other users' data
- CDN caching authenticated/personalized responses
- Unexpected public access to private resources
- IAM permission changes causing unexpected access
 
## Immediate response (first 10 minutes)
1. CONTAIN: block/disable the affected endpoint or purge cache immediately
2. ASSESS: determine scope — how many users, what data, what time window
3. NOTIFY: alert security team and on-call lead
4. PRESERVE: capture logs before any remediation that might overwrite them
 
## Fix: CDN cache serving wrong data
1. Purge entire CDN cache IMMEDIATELY:
```bash
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```
2. Revert CDN config to known-good version
3. Add `Cache-Control: no-store` at origin for all authenticated/personalized responses
4. Verify no caching on private routes: `curl -I <url> | grep cache`
 
## Fix: misconfigured access control
1. Identify the misconfigured resource and disable access immediately
2. Review IAM policies/resource policies for unintended `*` or public access
3. AWS S3 block public access:
```bash
aws s3api put-public-access-block --bucket <bucket> --public-access-block-configuration BlockPublicAcls=true,BlockPublicPolicy=true,IgnorePublicAcls=true,RestrictPublicBuckets=true
```
 
## Incident reporting (GDPR)
If personal data was exposed:
1. Document: what data, how many users, time window
2. File internal GDPR incident report within 24 hours
3. If high severity: notify DPA within 72 hours
4. Notify affected users per GDPR Article 34 if high risk
 
## Prevention
- Alert: CDN cache hit rate > 0% on /user/* or /account/* paths
- Regularly audit S3 bucket ACLs and public access settings
- Use AWS Config rules for compliance checks
- Add Cache-Control headers to all personalized endpoints at the framework level
""",
}


def write_incidents():
    out_dir = "data/incidents"
    os.makedirs(out_dir, exist_ok=True)

    for inc in INCIDENTS:
        path = os.path.join(out_dir, f"{inc['incident_id']}.json")
        with open(path, "w") as f:
            json.dump(inc, f, indent=2)
        print(f"[OK] Written {len(INCIDENTS)} incidents to {out_dir}/")


def write_runbooks():
    out_dir = "data/runbooks"
    os.makedirs(out_dir, exist_ok=True)
    for filename, content in RUNBOOKS.items():
        path = os.path.join(out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    print(f"[OK] Written {len(RUNBOOKS)} runbooks to {out_dir}/")


if __name__ == "__main__":
    write_incidents()
    write_runbooks()
    print("\nDataset ready. Next: python src/ingest.py")
