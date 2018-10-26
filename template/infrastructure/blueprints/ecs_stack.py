from stacker.blueprints.base import Blueprint
import stacker.blueprints.variables.types as types

from troposphere import (
    GetAtt,
    Ref,
    ec2,
    ecs,
    elasticloadbalancingv2 as elb,
    iam,
    logs,
    route53,
)


class EcsWebStack(Blueprint):
    """A blueprint for standing up a Web app on ECS with Fargate."""

    VARIABLES = {
        "Image": {
            "type": str,
            "description": "repo/image:tag for the image to run."
        },
        "ContainerEnvironment": {
            "type": dict,
            "description": "Dict of the environment for the container."
        },
        "DatabaseSecurityGroup": {
            "type": types.EC2SecurityGroupId,
            "description": "The database security group id."
        },
        # "Domain": {
        #     "type": str,
        #     "description": "The fully qualified domain for this service."
        # },
        # "DomainZoneId": {
        #     "type": str,
        #     "description": "The Route53 Zone ID to which add the domain."
        # },
        # "SslCertificateArn": {
        #     "type": str,
        #     "description": "The ARN for your SSL certificate."
        # },
        "Subnets": {
            "type": types.EC2SubnetIdList,
            "description": "Subnets for EC2 instances running ecs."
        },
        "VpcId": {
            "type": types.EC2VPCId,
            "description": "The ID of the VPC to launch Fargage."
        },
        "WebPort": {
            "type": str,
            "description": "The port to expose from the container to the web."
        },
    }

    @property
    def stacker_fqn(self):
        """Get the fully qualified stacker name."""
        return self.context.get_fqn(self.name)

    @property
    def variables(self):
        """Access the variables!"""
        return self.get_variables()

    @property
    def ecs_assumed_role_policy(self):
        """Assumed role policy doc for ECS"""
        return {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "",
                "Effect": "Allow",
                "Principal": {
                    "Service": "ecs-tasks.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }]
        }

    @property
    def task_role_policies(self):
        """Return policy to grant to our tasks which fall outside of the normal ECS operations.

        These policies are needed so that the command center can manage Route53, ACM and
        CloudFormation resources in order to setup client applications under a subdomain.

        """
        return [
            iam.Policy(
                PolicyName="CommandCenterStarPolicy",
                PolicyDocument={
                    "Statement": {
                        "Effect": "Allow",
                        "Action": [
                            "acm:ListCertificates",
                            "acm:RequestCertificate",
                            "cloudfront:CreateDistribution",
                            "cloudfront:GetDistribution",
                            "cloudfront:TagResource",
                            "route53:CreateHostedZone",
                            "route53:GetHostedZone",
                            "route53:GetChange",
                            "route53:ListHostedZones",
                        ],
                        "Resource": "*",
                    }
                }),
            iam.Policy(
                PolicyName="CommandCenterACMPolicy",
                PolicyDocument={
                    "Statement": {
                        "Effect": "Allow",
                        "Action": [
                            "acm:DescribeCertificate",
                        ],
                        "Resource": ["arn:aws:acm:us-east-1:*:certificate/*"],
                    }
                }),
            iam.Policy(
                PolicyName="CommandCenterRoute53ResourcePolicy",
                PolicyDocument={
                    "Statement": {
                        "Effect": "Allow",
                        "Action": [
                            "route53:ChangeResourceRecordSets",
                            "route53:ListResourceRecordSets",
                        ],
                        "Resource": [
                            "arn:aws:route53:::hostedzone/*",
                        ],
                    }
                }),
            iam.Policy(
                PolicyName="CommandCenterCFNPolicy",
                PolicyDocument={
                    "Statement": {
                        "Effect": "Allow",
                        "Action": [
                            "cloudformation:DescribeStacks",
                            "cloudformation:CreateStack",
                        ],
                        "Resource": [
                            "arn:aws:cloudformation:us-east-2:*:stack/*",
                        ],
                    }
                }),
        ]

    def build_environment(self, extra_env_vars=None):
        """Build the environment for the container."""
        if extra_env_vars is None:
            extra_env_vars = []

        envvars = self.get_variables()["ContainerEnvironment"]

        return extra_env_vars + [
            ecs.Environment(Name=key, Value=value) for key, value in envvars.iteritems()
        ]

    def create_log_group(self):
        """Create a CloudFormation log group."""
        return self.template.add_resource(
            logs.LogGroup("LogGroup", LogGroupName="%s-ecs" % (self.stacker_fqn)))

    def create_task_role(self):
        """Give our containers permissions to execute AWS APIs"""
        return self.template.add_resource(
            iam.Role(
                "TaskRole",
                RoleName="%s-%s" % ("ecsTaskRole", self.stacker_fqn),
                AssumeRolePolicyDocument=self.ecs_assumed_role_policy,
                Policies=self.task_role_policies))

    def create_task_execution_role(self):
        """This gives ECS tasks authority to manage Load Balancers as well as other things."""
        return self.template.add_resource(
            iam.Role(
                "TaskExecutionRole",
                RoleName="%s-%s" % ("ecsTaskExecRole", self.stacker_fqn),
                AssumeRolePolicyDocument=self.ecs_assumed_role_policy,
                ManagedPolicyArns=[
                    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
                ],
            ))

    def create_load_balancer_sg(self):
        """Create a security group for the load balancer."""
        return self.template.add_resource(
            ec2.SecurityGroup(
                "LoadBalancerSecurityGroup",
                GroupName="%s-load-balancer" % (self.stacker_fqn),
                GroupDescription="LoadBalancer Security Group for %s" % (self.stacker_fqn),
                SecurityGroupIngress=[
                    ec2.SecurityGroupRule(
                        CidrIp="0.0.0.0/0",
                        IpProtocol="tcp",
                        FromPort="80",
                        ToPort="80",
                    ),
                    ec2.SecurityGroupRule(
                        CidrIp="0.0.0.0/0",
                        IpProtocol="tcp",
                        FromPort="443",
                        ToPort="443",
                    )
                ],
                VpcId=Ref("VpcId")))

    def create_service_sg(self):
        """Create a security group for the service running our containers."""
        service_sg = self.template.add_resource(
            ec2.SecurityGroup(
                "EcsServiceSecurityGroup",
                GroupName="%s-ecs-service" % (self.stacker_fqn),
                GroupDescription="ECS Service Security Group for %s" % (self.stacker_fqn),
                SecurityGroupEgress=[
                    ec2.SecurityGroupRule(
                        CidrIp="0.0.0.0/0",
                        IpProtocol="-1",
                        FromPort="-1",
                        ToPort="-1",
                    ),
                ],
                SecurityGroupIngress=[
                    ec2.SecurityGroupRule(
                        CidrIp="0.0.0.0/0",
                        IpProtocol="tcp",
                        FromPort=self.variables["WebPort"],
                        ToPort=self.variables["WebPort"],
                    ),
                ],
                VpcId=Ref("VpcId")))

        self.template.add_resource(
            ec2.SecurityGroupIngress(
                "DatabaseSecurityGroupIngress",
                GroupId=Ref("DatabaseSecurityGroup"),
                FromPort="5432",
                ToPort="5432",
                IpProtocol="tcp",
                SourceSecurityGroupId=Ref(service_sg),
            ))

        return service_sg

    # def create_domain(self, app_lb):
    #     """Create domain record for our app!"""
    #     self.template.add_resource(
    #         route53.RecordSetType(
    #             "AppDomain",
    #             AliasTarget=route53.AliasTarget(
    #                 DNSName=GetAtt(app_lb, "DNSName"),
    #                 HostedZoneId=GetAtt(app_lb, "CanonicalHostedZoneID")),
    #             HostedZoneId=self.variables["DomainZoneId"],
    #             Name=self.variables["Domain"],
    #             Type="A",
    #         ))

    def create_app_load_balancer(self):
        """Create a load balancer for our app."""
        app_lb = self.template.add_resource(
            elb.LoadBalancer(
                "AppLoadBalancer",
                SecurityGroups=[Ref(self.create_load_balancer_sg())],
                Subnets=Ref("Subnets"),
                Type="application"))

        # self.create_domain(app_lb)

        app_lb_group = self.template.add_resource(
            elb.TargetGroup(
                "AppLoadBalancerTargetGroup",
                HealthCheckPath="/api/healthcheck",
                Port=self.variables["WebPort"],
                Protocol="HTTP",
                TargetType="ip",
                VpcId=Ref("VpcId")))

        app_http_listener = self.template.add_resource(
            elb.Listener(
                "AppHttpListener",
                DefaultActions=[elb.Action(TargetGroupArn=Ref(app_lb_group), Type="forward")],
                LoadBalancerArn=Ref(app_lb),
                Port=80,
                Protocol="HTTP",
            ))

        # app_https_listener = self.template.add_resource(
        #     elb.Listener(
        #         "AppHttpsListener",
        #         Certificates=[elb.Certificate(CertificateArn=self.variables["SslCertificateArn"])],
        #         DefaultActions=[elb.Action(TargetGroupArn=Ref(app_lb_group), Type="forward")],
        #         LoadBalancerArn=Ref(app_lb),
        #         Port=443,
        #         Protocol="HTTPS",
        #     ))

        ecs_balancer = ecs.LoadBalancer(
            ContainerName="web",
            ContainerPort=self.variables["WebPort"],
            TargetGroupArn=Ref(app_lb_group))

        # return {"ecs_balancer": ecs_balancer, "listeners": [app_http_listener, app_https_listener]}
        return {"ecs_balancer": ecs_balancer, "listeners": [app_http_listener]}

    def create_ecs_task(self, task_execution_role, task_role):
        """Create the ECS task definition"""
        container_defintion = ecs.ContainerDefinition(
            Name="web",
            Image=self.variables["Image"],
            Essential=True,
            Environment=self.build_environment(
                extra_env_vars=[ecs.Environment(Name="MASTER", Value="1")]),
            LogConfiguration=ecs.LogConfiguration(
                LogDriver="awslogs",
                Options={
                    "awslogs-region": Ref("AWS::Region"),
                    "awslogs-group": Ref(self.create_log_group()),
                    "awslogs-stream-prefix": self.stacker_fqn,
                    "awslogs-datetime-format": "%H:%M:%S"
                }),
            HealthCheck=ecs.HealthCheck(Command=[
                "CMD-SHELL",
                "curl -f http://localhost:%s/api/healthcheck || exit 1" % (self.variables["WebPort"])
            ]),
            PortMappings=[ecs.PortMapping(ContainerPort=self.variables["WebPort"])])

        return self.template.add_resource(
            ecs.TaskDefinition(
                "EcsTaskDefinition",
                Cpu="256",
                Family=self.stacker_fqn,
                Memory="512",
                NetworkMode="awsvpc",
                RequiresCompatibilities=["FARGATE"],
                ExecutionRoleArn=GetAtt(task_execution_role, "Arn"),
                TaskRoleArn=GetAtt(task_role, "Arn"),
                DependsOn=[task_execution_role, task_role],
                ContainerDefinitions=[container_defintion]))

    def create_ecs_service(self):
        """Create the ecs service that will serve up our app!"""
        cluster = self.template.add_resource(ecs.Cluster("Cluster"))
        load_balancer = self.create_app_load_balancer()
        task_execution_role = self.create_task_execution_role()
        task_role = self.create_task_role()

        self.template.add_resource(
            ecs.Service(
                "EcsService",
                DependsOn=load_balancer["listeners"],
                Cluster=Ref(cluster),
                DeploymentConfiguration=ecs.DeploymentConfiguration(
                    MaximumPercent=300, MinimumHealthyPercent=100),
                DesiredCount=1,
                LaunchType="FARGATE",
                TaskDefinition=Ref(self.create_ecs_task(task_execution_role, task_role)),
                LoadBalancers=[load_balancer["ecs_balancer"]],
                NetworkConfiguration=ecs.NetworkConfiguration(
                    AwsvpcConfiguration=ecs.AwsvpcConfiguration(
                        AssignPublicIp="ENABLED",
                        Subnets=Ref("Subnets"),
                        SecurityGroups=[Ref(self.create_service_sg())]))))

    def create_template(self):
        """Create the CFN template"""
        self.create_ecs_service()
