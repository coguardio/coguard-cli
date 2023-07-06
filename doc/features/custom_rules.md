% Custom Rules in CoGuard

Customers with the "Custom" Enterprise subscription can define custom
rules for their own software, or for existing software pieces. This
section describes the easiest way to create custom rules in CoGuard,
namely the predicate driven rules.

# Predicate driven rules

For each rule, one will create a separate JSON file. The JSON file
will have the following schema ([JSON-schema](http://json-schema.org)).

```json
{
  "definitions": {
    "keyObject": {
      "type": "object",
      "description": "A general object describing a special object in the key-path of a predicate rule.",
      "additionalProperties": false,
      "properties": {
        "key": {
          "type": "string",
          "description": "The key, formatted in a way as defined by the keyType enumeration."
        },
        "keyType": {
          "description": "Enum capturing the type of algorithm to be used for the interpretation of the key.",
          "enum": [
            "REGEX",
            "LISTREDUCER",
            "STRING",
            "INTERMEDIATEPATHVALUE"
          ]
        },
        "levelsMatching": {
          "type": "integer",
          "description": "Describes how many levels deep the matching of this regex still goes to remain a valid key path. Default is 1, and 0 means infinite.",
          "default": 1,
          "minimum": 0
        },
        "val": {
          "type": "string",
          "description": "If the `key` requires an extra value, it is stored here"
        }
      },
      "required": ["key", "keyType"]
    },
    "clause": {
      "description": "A clause contains an array of literals, as defined below.",
      "type": "object",
      "properties": {
        "literals": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/literal"
          }
        }
      },
      "additionalProperties": false,
      "required": [
        "literals"
      ]
    },
    "literal": {
      "type": "object",
      "description": "A literal is the heart of the whole rule. It defines keys and the properties of the values in configuration files",
      "properties": {
        "service": {"type": "string"},
        "configurationFile": {"type": "string"},
        "keyPath": {
          "type": "array", "items": {
            "anyOf": [
              { "type": "string" },
              { "#ref": "#/definitions/keyObject" }
            ]
          }
        },
        "operator": {"$ref": "#/definitions/operator"},
        "value": {"type": "string"},
        "default": {"type": "string"}
      },
      "additionalProperties": false,
      "required": [
        "service",
        "configurationFile",
        "keyPath",
        "operator"
      ]
    },
    "operator": {
      "description": "The supported set of operators to compare a value to a given expression.",
      "enum": [
        "keyShouldExist",
        "keyShouldNotExist",
        "is",
        "isNot",
        "all",
        "contains",
        "containsNot",
        "matches",
        "matchesNot",
        "matchesSome",
        "matchesNone",
        "matchesAll",
        "greater",
        "smaller"
      ]
    },
    "documentation": {
      "description": "A data type collecting necessary documentation information. The previous representation as string is deprecated.",
      "type": "object",
      "properties": {
        "documentation": {"type": "string"},
        "remediation": {"type": "string"},
        "sources": {
          "type": "array",
          "items": {"type": "string"}
        },
        "scenarios": {
          "type": "array",
          "items": {"type": "string"}
        }
      },
      "additionalProperties": false,
      "required": [
        "documentation",
        "remediation"
      ]
    }
  },

  "type": "object",
  "description": "A rule is a collection of clauses, evaluated in conjunction",
  "properties": {
    "identifier": {"type": "string"},
    "severity": {"type": "integer", "minimum": 1, "maximum": 5},
    "documentation": {
      "anyOf": [
        {"type": "string"},
        {"#ref": "#/definitions/documentation"}
      ]
    },
    "clauses": {
      "type": "array",
      "items": {
       "$ref": "#/definitions/clause"
      }
    }
  },
  "additionalProperties": false,
  "required": [
        "clauses", "severity", "identifier", "documentation"
  ]
}
```

# Simple example

Now take as an example a rule, `kerberos_default_tkt_enctypes`. In this schema, we would define it as following:

```json
{
  "identifier": "kerberos_default_tkt_enctypes",
  "severity": 3,
  "documentation": {
    "documentation": "One should not use the legacy TKT enctypes configuration.",
    "remediation": "`libdefaults` has a key called \"default_tkt_enctypes\". If this value is set, custom cryptographic mechanisms are set instead of default secure ones. The value should only be set for legacy systems.",
    "sources": [
      "https://web.mit.edu/kerberos/krb5-1.12/doc/admin/conf_files/krb5_conf.html"
    ]
  },
  "clauses": [
    {
      "literals": [
        {
          "service": "kerberos",
          "configurationFile": "krb5.conf",
          "keyPath": [
            "libdefaults",
            "default_tkt_enctypes"
          ],
          "operator": "keyShouldNotExist"
        }
      ]
    }
  ]
}
```

# More complicated example
Take AWS’s cloudformation files.

```yaml
Resources:
  Deployment:
    DependsOn: MyMethod
    Type: 'AWS::ApiGateway::Deployment'
    Properties:
      RestApiId: !Ref MyApi
      Description: My deployment
      StageName: DummyStage
      StageDescription:
        CacheDataEncrypted: true
  MyLoadBalancer:
      Type: AWS::ElasticLoadBalancing::LoadBalancer
      Properties:
        AvailabilityZones:
        - "us-east-2a"
        CrossZone: true
        Listeners:
        - InstancePort: '80'
          InstanceProtocol: HTTP
          LoadBalancerPort: '443'
          Protocol: HTTPS
          PolicyNames:
          - My-SSLNegotiation-Policy
          SSLCertificateId: arn:aws:iam::123456789012:server-certificate/my-server-certificate
        HealthCheck:
          Target: HTTP:80/
          HealthyThreshold: '2'
          UnhealthyThreshold: '3'
          Interval: '10'
          Timeout: '5'
        Policies:
        - PolicyName: My-SSLNegotiation-Policy
          PolicyType: SSLNegotiationPolicyType
          Attributes:
          - Name: Reference-Security-Policy
            Value: ELBSecurityPolicy-TLS-1-2-2017-01
```
And say, we wish to evaluate the rule which states that every resource
of type `AWS::ApiGateway::Deployment` has to have the
property `StageDescription` with `CacheEnabled` being
true. This is achieved by

```json
"clauses": [
    {
      "literals": [
        {
          "service": "cloudformation",
          "configurationFile": "aws_template.yaml",
          "keyPath": [
            "Resources",
            {"key": ".+", "keyType": "REGEX"},
            {"keyType": "INTERMEDIATEPATHVALUE", "key": "Type", "val": "AWS::ApiGateway::Deployment"}
            "Properties",
            "StageDescription",
            "CacheDataEncrypted"
          ],
          "operator": "is",
          "value": "true",
          "default": "false"
        }
      ]
    }
  ]
```
