import aminator.util.linux
import unittest
import os
import logging
import shutil
import tempfile

log = logging.getLogger(__name__)
logging.root.addHandler(logging.StreamHandler())
logging.root.setLevel(logging.DEBUG)


class linux_util(unittest.TestCase):
    src_root = tempfile.mkdtemp(dir='/tmp', prefix='src_')
    dst_root = tempfile.mkdtemp(dir='/tmp', prefix='dst_')

    files = ['a', 'b', 'c', 'd', 'Da', 'Db', 'Dc', 'Dd']

    def test_provision_configs(self):
        """ test install_provision_configs and remove_provision_configs against
        self.files.
        Test matrix:
            files    src_exists     dst_exists
            a            y              y
            b            y              n
            c            n              y
            d            n              n
            Da           y              y
            Db           y              n
            Dc           n              y
            Dd           n              n
        """
        # create /dst_root/src_root
        dst_dir = os.path.join(self.dst_root, self.src_root.lstrip('/'))
        os.makedirs(dst_dir)
        # /src_root/{a,b}
        open(os.path.join(self.src_root, 'a'), 'w').close()
        open(os.path.join(self.src_root, 'b'), 'w').close()

        # dirs /src_root/{Da/a,{Db/b}
        os.mkdir(os.path.join(self.src_root, 'Da'))
        open(os.path.join(self.src_root, 'Da', 'a'), 'w').close()
        os.mkdir(os.path.join(self.src_root, 'Db'))
        open(os.path.join(self.src_root, 'Db', 'b'), 'w').close()
        
        # /dst_root/src_root/{a,c}
        open(os.path.join(dst_dir, 'a'), 'w').close()
        open(os.path.join(dst_dir, 'c'), 'w').close()

        # dirs /dst_root/src_root/{Da/a,{Dc/c}
        os.mkdir(os.path.join(dst_dir, 'Da'))
        open(os.path.join(dst_dir, 'Da', 'a'), 'w').close()
        os.mkdir(os.path.join(dst_dir, 'Dc'))
        open(os.path.join(dst_dir, 'Dc', 'c'), 'w').close()

        provision_config_files = [os.path.join(self.src_root, x) for x in self.files]

        install_status = aminator.util.linux.install_provision_configs(provision_config_files, self.dst_root)
        remove_status = aminator.util.linux.remove_provision_configs(provision_config_files, self.dst_root)

        shutil.rmtree(self.src_root)
        shutil.rmtree(self.dst_root)

        assert install_status & remove_status


if __name__ == "__main__":
        unittest.main()
