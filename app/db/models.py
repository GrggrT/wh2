from tortoise import models, fields

class User(models.Model):
    """Модель пользователя"""
    id = fields.IntField(pk=True)
    telegram_id = fields.BigIntField(unique=True)
    username = fields.CharField(max_length=50, null=True)
    timezone = fields.CharField(max_length=50, default="UTC")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self):
        return f"User {self.telegram_id}"

class Workplace(models.Model):
    """Модель рабочего места"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="workplaces")
    name = fields.CharField(max_length=100)
    rate = fields.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "workplaces"

    def __str__(self):
        return self.name

class Record(models.Model):
    """Модель записи рабочего времени"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="records")
    workplace = fields.ForeignKeyField("models.Workplace", related_name="records", null=True)
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField(null=True)
    description = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "records"

    def __str__(self):
        return f"Record {self.id} - {self.start_time}" 