'use strict';
require('./worker.cjs').cli().catch(e=>{console.error(String(e.message||e));process.exit(1);});
