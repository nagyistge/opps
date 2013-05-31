#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone

from .signals import shorturl_generate, delete_container
from opps.core.cache import _cache_key
from opps.core.models import Publishable, Slugged, Channeling
from opps.boxes.models import BaseBox

from taggit.managers import TaggableManager


class Container(Publishable, Slugged, Channeling):
    title = models.CharField(_(u"Title"), max_length=140, db_index=True)
    hat = models.CharField(
        _(u"Hat"),
        max_length=140,
        null=True, blank=True,
    )
    short_url = models.URLField(
        _("Short URL"),
        null=True, blank=True,
    )
    child_class = models.CharField(
        _(u'Child class'),
        max_length=30,
        null=True, blank=True,
        db_index=True
    )
    child_app_label = models.CharField(
        _(u'Child app label'),
        max_length=30,
        null=True, blank=True,
        db_index=True
    )
    tags = TaggableManager(blank=True, verbose_name=u'Tags')
    show_on_root_channel = models.BooleanField(
        _(u"Show on root channel?"),
        default=True
    )
    sources = models.ManyToManyField(
        'sources.Source',
        null=True, blank=True,
        through='containers.ContainerSource')

    def __unicode__(self):
        return u"{}".format(self.get_absolute_url())

    class Meta:
        ordering = ['-date_available', 'title', 'channel_long_slug']
        verbose_name = _('Container')
        verbose_name_plural = _('Containers')
        unique_together = ("site", "child_class", "channel_long_slug", "slug")

    def save(self, *args, **kwargs):
        self.channel_name = self.channel.name
        self.channel_long_slug = self.channel.long_slug
        self.child_class = self.__class__.__name__
        self.child_app_label = self._meta.app_label

        models.signals.post_save.connect(shorturl_generate,
                                         sender=self.__class__)
        super(Container, self).save(*args, **kwargs)

    def get_absolute_url(self):
        """
        TODO: get_absolute_url from child_app_label/child_class
        """
        if self.child_class != "Post":
            return "/{}/{}/{}".format(self.child_class.lower(),
                                      self.channel_long_slug, self.slug)
        return "/{}/{}".format(self.channel_long_slug, self.slug)

    def get_thumb(self):
        return self.main_image

    @property
    def search_category(self):
        """for use in search result"""
        return _(self.child_class)

    def get_http_absolute_url(self):
        return "http://{}{}".format(self.site_domain, self.get_absolute_url())
    get_http_absolute_url.short_description = 'URL'

    def recommendation(self):
        cachekey = _cache_key(
            '{}-recommendation'.format(self.__class__.__name__),
            self.__class__, self.site_domain,
            u"{}-{}".format(self.channel_long_slug, self.slug))
        getcache = cache.get(cachekey)
        if getcache:
            return getcache

        tag_list = [t for t in self.tags.all()[:3]]
        _list = [a for a in Container.objects.filter(
            site_domain=self.site_domain,
            child_class=self.child_class,
            channel_long_slug=self.channel_long_slug,
            date_available__lte=timezone.now(),
            published=True,
            tags__in=tag_list).exclude(
                pk=self.pk).distinct().all().order_by('pk')[:10]]

        cache.set(cachekey, _list)
        return _list


class ContainerSource(models.Model):
    container = models.ForeignKey(
        'containers.Container',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='containersource_containers',
        verbose_name=_(u'Container'),
    )
    source = models.ForeignKey(
        'sources.Source',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='containersource_sources',
        verbose_name=_(u'Source'),
    )
    order = models.PositiveIntegerField(_(u'Order'), default=0)

    class META:
        verbose_name = _(u'Container source')
        verbose_name_plural = _(u'Container sources')
        ordering = ('order',)

    def __unicode__(self):
        return u"{}".format(self.source.slug)


class ContainerImage(models.Model):
    container = models.ForeignKey(
        'containers.Container',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='containerimage_containers',
        verbose_name=_(u'Container'),
    )
    image = models.ForeignKey(
        'images.Image',
        verbose_name=_(u'Image'),
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    order = models.PositiveIntegerField(_(u'Order'), default=0)

    class META:
        verbose_name = _('Container image')
        verbose_name_plural = _('Container images')
        ordering = ('order',)

    def __unicode__(self):
        return u"{}".format(self.image.title)


class ContainerBox(BaseBox):

    title = models.CharField(
        _(u"Title"),
        null=True,
        blank=True,
        max_length=140,
    )
    container = models.ManyToManyField(
        'containers.Container',
        null=True, blank=True,
        related_name='containerbox_containers',
        through='containers.ContainerBoxContainers'
    )
    queryset = models.ForeignKey(
        'boxes.QuerySet',
        null=True, blank=True,
        related_name='containerbox_querysets',
        verbose_name=_(u'Query Set')
    )

    class META:
        verbose_name = _('Container box')
        verbose_name_plural = _('Containers boxes')

    def ordered_articles(self, field='order'):
        now = timezone.now()
        qs = self.articles.filter(
            published=True,
            date_available__lte=now,
            containerboxcontainers_containers__date_available__lte=now
        ).filter(
            models.Q(containerboxcontainers_containers__date_end__gte=now) |
            models.Q(containerboxcontainers_containers__date_end__isnull=True)
        )
        return qs.order_by('containerboxcontainers_containers__order'
                           ).distinct()

    def get_queryset(self):
        """
        for backwards compatibility
        """
        return self.queryset.get_queryset()


class ContainerBoxContainers(models.Model):
    containerbox = models.ForeignKey(
        'containers.ContainerBox',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='articleboxarticles_articleboxes',
        verbose_name=_(u'Article Box'),
    )
    container = models.ForeignKey(
        'containers.Container',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='containerboxcontainers_containers',
        verbose_name=_(u'Container'),
    )
    order = models.PositiveIntegerField(_(u'Order'), default=0)
    date_available = models.DateTimeField(_(u"Date available"),
                                          default=timezone.now, null=True)
    date_end = models.DateTimeField(_(u"End date"), null=True, blank=True)

    class Meta:
        ordering = ('order',)
        verbose_name = _('Article box articles')
        verbose_name_plural = _('Article boxes articles')

    def __unicode__(self):
        return u"{0}-{1}".format(self.articlebox.slug, self.article.slug)

    def clean(self):

        if not self.article.published:
            raise ValidationError(_(u'Article not published!'))


models.signals.post_delete.connect(delete_container, sender=Container)
