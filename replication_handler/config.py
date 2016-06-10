# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging
import os

import staticconf
import yelp_conn
from yelp_servlib import clog_util
from yelp_servlib.config_util import load_default_config


logger = logging.getLogger('replication_handler.config')


class BaseConfig(object):
    """
    Staticconf base object for managing config
    TODO: (cheng|DATAPIPE-88) Removed the config reloading code,
    will work on that later.
    """

    def __init__(
            self,
            config_path='config.yaml',
            env_config_path='config-env-dev.yaml'
    ):
        self.service_config_path = os.environ.get(
            'SERVICE_CONFIG_PATH',
            config_path
        )
        self.service_env_config_path = os.environ.get(
            'SERVICE_ENV_CONFIG_PATH', env_config_path
        )
        logger.info("loading service config from {s}".format(
            s=self.service_config_path)
        )
        logger.info("Loading env service config from {s}".format(
            s=self.service_env_config_path)
        )
        load_default_config(
            self.service_config_path,
            self.service_env_config_path
        )
        yelp_conn.initialize()
        clog_util.initialize()


class EnvConfig(BaseConfig):
    """
    When we do staticconf.get(), we will get a ValueProxy object,
    sometimes it is not accepted, so by calling value on that we will get
    its original value.
    """

    @property
    def container_name(self):
        return os.environ.get(
            'PAASTA_INSTANCE',
            staticconf.get('container_name').value
        )

    @property
    def container_env(self):
        return os.environ.get(
            'PAASTA_CLUSTER',
            staticconf.get('container_env').value
        )

    @property
    def namespace(self):
        return staticconf.get('namespace').value

    @property
    def rbr_source_cluster(self):
        return staticconf.get('rbr_source_cluster').value

    @property
    def schema_tracker_cluster(self):
        return staticconf.get('schema_tracker_cluster').value

    @property
    def rbr_state_cluster(self):
        return staticconf.get('rbr_state_cluster').value

    @property
    def register_dry_run(self):
        return staticconf.get('register_dry_run').value

    @property
    def publish_dry_run(self):
        return staticconf.get('publish_dry_run').value

    @property
    def topology_path(self):
        return staticconf.get('topology_path').value

    @property
    def schema_blacklist(self):
        return staticconf.get('schema_blacklist').value

    @property
    def table_whitelist(self):
        return staticconf.get('table_whitelist', default=None).value

    # TODO This config is never used in setting up the replication handler.
    # Its set in the clientlibs/data_pipeline hence to be removed.
    @property
    def zookeeper_discovery_path(self):
        return staticconf.get('zookeeper_discovery_path').value

    @property
    def producer_name(self):
        return staticconf.get('producer_name').value

    @property
    def team_name(self):
        return staticconf.get('team_name').value

    @property
    def pii_yaml_path(self):
        return staticconf.get('pii_yaml_path').value

    @property
    def max_delay_allowed_in_minutes(self):
        return staticconf.get('max_delay_allowed_in_minutes').value

    @property
    def sensu_host(self):
        """If we're running in Paasta, use the paasta cluster from the
        environment directly as laid out in PAASTA-1579.  This makes it so that
        local-run and real sensu alerts go to the same cluster, which should
        prevent false alerts that never resolve when we run locally.
        """
        if os.environ.get('PAASTA_CLUSTER'):
            return "paasta-{cluster}.yelp".format(
                cluster=os.environ.get('PAASTA_CLUSTER')
            )
        else:
            return staticconf.get('sensu_host').value

    @property
    def sensu_source(self):
        """This ensures that the alert tracks both the paasta environment and
        the running instance, so we can have separate alerts for the pnw-prod
        canary and the pnw-devc main instances.
        """
        return 'replication_handler_{container_env}_{container_name}'.format(
            container_env=self.container_env,
            container_name=self.container_name
        )

    @property
    def disable_sensu(self):
        return staticconf.get('disable_sensu').value

    @property
    def disable_meteorite(self):
        return staticconf.get('disable_meteorite').value

    @property
    def recovery_queue_size(self):
        # The recovery queue size have to be greater than data pipeline producer
        # buffer size, otherwise we could potentially have stale checkpoint data which
        # would cause the recovery process to fail.
        return staticconf.get('recovery_queue_size').value

    @property
    def resume_stream(self):
        """Controls if the replication handler will attempt to resume from
        an existing position, or start from the beginning of replication.  This
        should almost always be True.  The two exceptions are when dealing
        with a brand new database that has never had any tables created, or
        when running integration tests.

        We may want to make this always True, and otherwise bootstrap the
        replication handler for integration tests.  Even "schemaless" databases
        likely have Yelp administrative tables, limiting the usefuleness of
        this in practice.
        """
        return staticconf.get_bool('resume_stream', default=True).value

    @property
    def resume_from_log_position(self):
        """
        If set to true, when the replication handler restarts, it will resume
        from the log position that is saved in the log_position_state table
        """
        return staticconf.get_bool(
            'resume_from_log_position',
            default=True
        ).value

    @property
    def force_exit(self):
        """Determines if we should force an exit, which can be helpful if we'd
        otherwise block waiting for replication events that aren't going to come.

        In general, this should be False in prod environments, and True in test
        environments.
        """
        return staticconf.get_bool('force_exit').value


class DatabaseConfig(object):
    """
    Used for reading database config out of topology.yaml in the environment
    """

    def __init__(self, cluster_name, topology_path):
        load_default_config(topology_path)
        self._cluster_name = cluster_name

    @property
    def cluster_config(self):
        for topo_item in staticconf.get('topology'):
            if topo_item.get('cluster') == self.cluster_name:
                return topo_item

    @property
    def entries(self):
        return self.cluster_config['entries']

    @property
    def cluster_name(self):
        return self._cluster_name


class SourceDatabaseConfig(DatabaseConfig):

    def __init__(self, cluster_name, topology_path):
        DatabaseConfig.__init__(self, cluster_name, topology_path)


class SchemaTrackingDatabaseConfig(DatabaseConfig):

    def __init__(self, cluster_name, topology_path):
        DatabaseConfig.__init__(self, cluster_name, topology_path)

env_config = EnvConfig()

source_database_config = SourceDatabaseConfig(
    env_config.rbr_source_cluster,
    env_config.topology_path
)
schema_tracking_database_config = SchemaTrackingDatabaseConfig(
    env_config.schema_tracker_cluster,
    env_config.topology_path
)
