#!/usr/bin/env python3
import aws_cdk as cdk
from ma3t_stack import Ma3tStack

app = cdk.App()
Ma3tStack(app, "Ma3tStack")
app.synth()
