# Firewall Guide (Single Source) - Terraform IaC

**📚 For comprehensive security analysis, see:** [DOCS_TECHNICAL_WAF_CONFIGURATION.md](DOCS_TECHNICAL_WAF_CONFIGURATION.md)

---

## Current Target State

WAF is attached to the ALB with exactly 5 rules:

1. `RateLimitRule` (rate-based, 2000 requests/5min/IP)
2. `AWS-AWSManagedRulesSQLiRuleSet`
3. `AWS-AWSManagedRulesKnownBadInputsRuleSet`
4. `AWS-AWSManagedRulesCommonRuleSet`
5. `AWS-AWSManagedRulesAmazonIpReputationList`

Region: `us-west-2`

---

## AWS Console Quick Control

### Turn WAF protection ON/OFF

1. Open AWS Console -> WAF & Shield -> Web ACLs
2. Select `rag-pipeline-waf`
3. Open `Associated resources`
4. To turn ON: `Add AWS resource` -> choose your ALB -> `Add`
5. To turn OFF: remove ALB association from this tab

Note: This only associates/disassociates WAF. It does not delete your rule set.

---

## Terraform Source of Truth (Now Updated)

Terraform now includes WAF in:

- `terraform/main.tf`
- `terraform/variables.tf`
- `terraform/outputs.tf`
- `terraform/modules/waf/main.tf`

`terraform/terraform.tfvars.example` includes WAF settings:

```hcl
enable_waf = true
waf_name = "rag-pipeline-waf"
waf_rate_limit_requests_per_5_minutes = 2000
waf_enable_logging = true
waf_log_retention_days = 30
```

---

## Adopt Existing Manual WAF into Terraform State

If the WAF was created manually in AWS first, import it before `terraform apply`.

From `Phase_2_FE_AI_Merge/terraform`:

```powershell
terraform init
```

### 1) Import Web ACL

```powershell
terraform import 'module.waf[0].aws_wafv2_web_acl.this' '<WEB_ACL_ID>/<WEB_ACL_NAME>/REGIONAL'
```

Example:

```powershell
terraform import 'module.waf[0].aws_wafv2_web_acl.this' 'a1b2c3d4-1111-2222-3333-abcdef123456/rag-pipeline-waf/REGIONAL'
```

### 2) Import ALB association

```powershell
terraform import 'module.waf[0].aws_wafv2_web_acl_association.alb' '<ALB_ARN>,<WEB_ACL_ARN>'
```

### 3) Import log group (if logging enabled)

```powershell
terraform import 'module.waf[0].aws_cloudwatch_log_group.waf[0]' '/aws/wafv2/rag-pipeline-waf'
```

### 4) Import logging configuration (if enabled)

```powershell
terraform import 'module.waf[0].aws_wafv2_web_acl_logging_configuration.this[0]' '<WEB_ACL_ARN>'
```

---

## Validate and Apply

```powershell
terraform fmt -recursive
terraform validate
terraform plan
```

Expected result after successful import: plan should be minimal or no-op for existing WAF resources.

---

## Verify

### Terraform outputs

```powershell
terraform output waf_web_acl_name
terraform output waf_web_acl_arn
terraform output waf_log_group_name
```

### AWS Console

1. WAF -> Web ACLs -> `rag-pipeline-waf`
2. Confirm 5 rules listed in order
3. Confirm ALB appears in `Associated resources`
4. Check CloudWatch log group `/aws/wafv2/rag-pipeline-waf`

---

## Cost-Safe Recommendation

Keep only the current 5-rule baseline for now. This is strong and cost-effective.

- Required now: the 5 existing free/standard managed rules + rate limit
- Optional later: Bot Control only if logs show real bot pressure
- Avoid now: Shield Advanced unless your threat model truly requires enterprise DDoS response
