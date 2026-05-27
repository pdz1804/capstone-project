# Custom domain, ACM, and ALB (production checklist)

This document records how public DNS (Hostinger), AWS Certificate Manager (ACM), and the Application Load Balancer (ALB) are wired together for the project. Use it when reissuing certs, changing DNS, or debugging HTTPS.

## Architecture (logical flow)

1. **ACM** issues a **public** TLS certificate in the **same AWS Region as the ALB** (e.g. `us-west-2`).
2. **DNS validation**: for each name on the certificate (apex and `www`), ACM shows a **CNAME name** and **CNAME value** (target under `*.acm-validations.aws`).
3. You add those records in the **registrar/DNS host** (Hostinger → DNS records).
4. After validation succeeds, ACM shows **Issued**; you attach the certificate to the ALB **HTTPS:443** listener.
5. You point **your domain** at the ALB **DNS name** (not the IP): apex via **ALIAS/ANAME** (if the provider supports it) or provider-specific apex mapping; `www` via **CNAME** to the same ALB hostname.

## Reference configuration (as deployed)

| Piece | Detail |
|--------|--------|
| ALB name | `rag-pipeline-alb` |
| ALB DNS (example) | `rag-pipeline-alb-1719237910.us-west-2.elb.amazonaws.com` |
| Region | `us-west-2` (Oregon)   ALB DNS name must match this region |
| Certificate scope | `k2p-bkmind-learning-platform.com` and `www.k2p-bkmind-learning-platform.com` |
| HTTP :80 | Redirect **301** to **HTTPS** on **443** (force TLS) |
| HTTPS :443 | Forwards to target group (e.g. frontend); ACM cert on listener; TLS policy e.g. `ELBSecurityPolicy-TLS13-1-2-2021-06` |

Hostinger-style DNS table:

| Type | Host / name | Points to |
|------|----------------|-----------|
| CNAME | ACM validation label (from console) | ACM validation target `.acm-validations.aws` |
| CNAME | ACM validation label for second name | Second ACM validation target |
| ALIAS | `@` (apex) | ALB DNS name |
| CNAME | `www` | Same ALB DNS name |

Exact **host** field at providers varies: some want the full `_xxx.example.com`, some only the `_xxx` prefix. Follow Hostinger’s help text; the **resolved record** must match what ACM expects.

## Correctness checks

- **ACM certificate**: Status **Issued**; each domain **Validation status: Success**; **In use: Yes** on the ALB listener you expect.
- **DNS to ALB**: `dig` / online DNS checker shows apex and `www` **CNAME** (or ALIAS) to the **elb.amazonaws.com** name.
- **HTTPS in browser**: Valid chain, no name mismatch, no expired certificate.
- **HTTP**: Visiting `http://` redirects to `https://` (301).

## Operational notes

- **Exact strings**: Validation CNAME **name** and **value** must match ACM **character-for-character**. If you replace the certificate or request a new one, **update** both DNS rows from the **new** ACM instructions.
- **Keep validation records**: Leaving validation CNAMEs in place supports ACM **renewal** for DNS-validated public certs.
- **Expiry**: Confirm **Not after** in ACM periodically; renew/replace before expiry.
- **Listener rules**: If the **default** action only forwards to the **frontend** target group, API traffic must be routed by **additional rules** (path or host) to the **backend** target group when the API is not served from the same group.

## Troubleshooting (short)

| Symptom | Likely cause |
|---------|----------------|
| ACM stuck **Pending validation** | Wrong validation CNAME, typo, or record at wrong zone/wrong provider |
| **Certificate mismatch** in browser | Connecting to a listener or alias that uses a different cert, or hitting ALB by wrong hostname |
| Apex does not resolve | Registrar still on old NS; apex needs ALIAS/ANAME, plain CNAME at apex often invalid |
| 502 / unhealthy | Target group health checks failing, not a DNS/cert issue |

## Related repo docs

- `AWS_DEPLOYMENT_SETUP.md`   broader Terraform, ECS, and CI/CD context
- `Phase_2_FE_AI_Merge/terraform/`   ALB and listener definitions as code (keep code and console in sync when possible)

---

*Extracted from team runbook / console verification; update this file when the domain, ALB name, or certificate ARN changes.*
