#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.utils import timezone
from django.conf import settings

from tastypie.resources import ModelResource
from tastypie.constants import ALL

from opps.api import MetaBase

from .models import Container as ContainerModel
from .models import ContainerBox as ContainerBoxModel
from .models import ContainerBoxContainers


class Container(ModelResource):
    class Meta(MetaBase):
        queryset = ContainerModel.objects.filter(
            published=True,
            date_available__lte=timezone.now()
        ).exclude(child_class__in=settings.OPPS_CONTAINERS_BLACKLIST)

    def dehydrate_child_class(self, bundle):
        return bundle.data['child_class'].lower()

    def dehydrate_resource_uri(self, bundle):
        return u"/api/{}/{}/{}/".format(
            self.api_name,
            bundle.data['child_class'].lower(),
            bundle.data['id'])


class ContainerBoxItens(ModelResource):
    class Meta:
        queryset = ContainerBoxContainers.objects.all()
        allowed_methods = ['get']
        filtering = {
            "containerbox": ALL
        }


class ContainerBox(ModelResource):
    class Meta(MetaBase):
        queryset = ContainerBoxModel.objects.filter(
            published=True,
            date_available__lte=timezone.now()
        )