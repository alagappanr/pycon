from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from symposion.proposals.models import ProposalBase
from symposion.conference.models import Section


class Schedule(models.Model):

    section = models.OneToOneField(Section)
    published = models.BooleanField(default=True)

    def __unicode__(self):
        return u"%s Schedule" % self.section


class Day(models.Model):

    schedule = models.ForeignKey(Schedule)
    date = models.DateField()

    def __unicode__(self):
        return u"%s" % self.date

    class Meta:
        unique_together = [("schedule", "date")]


class Room(models.Model):

    schedule = models.ForeignKey(Schedule)
    name = models.CharField(max_length=65)
    order = models.PositiveIntegerField()

    def __unicode__(self):
        return self.name


class SlotKind(models.Model):
    """
    A slot kind represents what kind a slot is. For example, a slot can be a
    break, lunch, or X-minute talk.
    """

    schedule = models.ForeignKey(Schedule)
    label = models.CharField(max_length=50)

    def __unicode__(self):
        return self.label


class Slot(models.Model):

    day = models.ForeignKey(Day)
    kind = models.ForeignKey(SlotKind)
    start = models.TimeField()
    end = models.TimeField()
    content_override = models.TextField(blank=True)

    def assign(self, content):
        """
        Assign the given content to this slot and if a previous slot content
        was given we need to unlink it to avoid integrity errors.
        """
        self.unassign()
        content.slot = self
        content.save()

    def unassign(self):
        """
        Unassign the associated content with this slot.
        """
        if self.content and self.content.slot_id:
            self.content.slot = None
            self.content.save()

    @property
    def duration(self):
        start_dt = datetime.strptime(self.start.isoformat(), "%H:%M:%S")
        end_dt = datetime.strptime(self.end.isoformat(), "%H:%M:%S")
        delta = end_dt - start_dt
        return delta.seconds // 60

    @property
    def content(self):
        """
        Return the content this slot represents.
        @@@ hard-coded for presentation for now
        """
        try:
            return self.content_ptr
        except ObjectDoesNotExist:
            return None

    @property
    def rooms(self):
        return Room.objects.filter(pk__in=self.slotroom_set.values("room")).order_by('name')

    @property
    def start_date(self):
        return datetime.combine(self.day.date, self.start)

    @property
    def end_date(self):
        return datetime.combine(self.day.date, self.end)

    def __unicode__(self):
        return u"%s %s (%s - %s)" % (self.day, self.kind, self.start, self.end)

    class Meta:
        ordering = ["day", "start", "end"]


class SlotRoom(models.Model):
    """
    Links a slot with a room.
    """

    slot = models.ForeignKey(Slot)
    room = models.ForeignKey(Room)

    def __unicode__(self):
        return u"%s %s" % (self.room, self.slot)

    class Meta:
        unique_together = [("slot", "room")]
        ordering = ["slot", "room__order"]


class Presentation(models.Model):

    slot = models.OneToOneField(Slot, null=True, blank=True, related_name="content_ptr")
    title = models.CharField(max_length=100)
    description = models.TextField()
    abstract = models.TextField()
    speaker = models.ForeignKey("speakers.Speaker", related_name="presentations")
    additional_speakers = models.ManyToManyField("speakers.Speaker", related_name="copresentations", blank=True)
    cancelled = models.BooleanField(default=False)
    proposal_base = models.OneToOneField(ProposalBase, related_name="presentation")
    section = models.ForeignKey(Section, related_name="presentations")

    @property
    def number(self):
        return self.proposal.number

    @property
    def proposal(self):
        if self.proposal_base_id is None:
            return None
        return ProposalBase.objects.get_subclass(pk=self.proposal_base_id)

    def speakers(self):
        yield self.speaker
        for speaker in self.additional_speakers.all():
            if speaker.user:
                yield speaker

    def __unicode__(self):
        return u"#%s %s (%s)" % (self.number, self.title, self.speaker)

    class Meta:
        ordering = ["slot"]
