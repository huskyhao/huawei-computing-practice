#define _GNU_SOURCE
#include "kernels.h"
#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static volatile uint64_t sink;
static uint64_t rng_state = UINT64_C(0x92020261104);
static uint64_t random_u64(void) {
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 7;
    rng_state ^= rng_state << 17;
    return rng_state;
}
static void fail(const char *message) { fprintf(stderr,"ERROR %s\n",message); exit(1); }
static double now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC_RAW,&t)) fail("clock_gettime");
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

/* Query only: nodes=NULL, flags=0. This never requests page migration. */
static void verify_pages(void *buffer,size_t bytes,int expected,const char *phase,int cpu) {
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0 || bytes % (size_t)page_size) fail("invalid page size");
    size_t count = bytes / (size_t)page_size;
    void **pages = malloc(count * sizeof(*pages));
    int *status = malloc(count * sizeof(*status));
    if (!pages || !status) fail("page query allocation");
    for (size_t i=0;i<count;++i) {
        pages[i]=(char *)buffer+i*(size_t)page_size; status[i]=-999;
    }
    if (syscall(SYS_move_pages,0,count,pages,NULL,status,0) < 0) {
        perror("move_pages query"); exit(1);
    }
    size_t counts[4]={0,0,0,0};
    for (size_t i=0;i<count;++i) {
        if (status[i] < 0 || status[i] > 3) fail("unavailable page status");
        ++counts[status[i]];
        if (status[i] != expected) fail("page is outside requested memory node");
    }
    printf("PLACEMENT,%s,%d,%d,%zu,%ld,%zu,%zu,%zu,%zu\n",phase,cpu,expected,count,page_size,
           counts[0],counts[1],counts[2],counts[3]);
    fflush(stdout);
    free(status); free(pages);
}

static double batch(const uint64_t *data,size_t words,size_t slots,int pattern,
                    size_t reps,uint64_t expected) {
    uint64_t checksum=0;
    double start=now();
    for (size_t r=0;r<reps;++r)
        checksum += pattern ? chase_cycle(data,slots) : scan_sum(data,words);
    double elapsed=now()-start;
    sink=checksum;
    if (checksum != expected*(uint64_t)reps) fail("batch checksum mismatch");
    return elapsed;
}

int main(int argc,char **argv) {
    if (argc != 5) fail("usage: bench cpu memory_node rounds MiB");
    int cpu=atoi(argv[1]),node=atoi(argv[2]),rounds=atoi(argv[3]);
    size_t mib=(size_t)strtoull(argv[4],NULL,10);
    if (cpu<0 || cpu>=CPU_SETSIZE || node<0 || node>3 || rounds<1 || rounds>101 || mib<1 || mib>512)
        fail("invalid configuration");
    cpu_set_t mask;
    if (sched_getaffinity(0,sizeof(mask),&mask) || CPU_COUNT(&mask)!=1 || !CPU_ISSET(cpu,&mask))
        fail("launch under numactl --physcpubind=CPU --membind=NODE");
    size_t bytes=mib*1024*1024,words=bytes/sizeof(uint64_t),slots=bytes/128;
    uint64_t *data=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if (data==MAP_FAILED) { perror("mmap"); return 1; }
    if (madvise(data,bytes,MADV_NOHUGEPAGE)) { perror("madvise NOHUGEPAGE"); return 1; }
    for (size_t i=0;i<words;++i) data[i]=1;
    uint32_t *order=malloc(slots*sizeof(*order));
    if (!order) fail("permutation allocation");
    for (size_t i=0;i<slots;++i) order[i]=(uint32_t)i;
    for (size_t i=slots-1;i>0;--i) {
        size_t j=(size_t)(random_u64()%(i+1));
        uint32_t tmp=order[i]; order[i]=order[j]; order[j]=tmp;
    }
    for (size_t i=0;i<slots;++i) data[(size_t)order[i]*16]=order[(i+1)%slots];
    free(order);
    uint64_t expected=(uint64_t)slots*(slots-1)/2+(uint64_t)slots*15;
    if (scan_sum(data,words)!=expected) fail("initial sequential sum");
    unsigned char *seen=calloc((slots+7)/8,1);
    if (!seen) fail("cycle verification allocation");
    uint64_t index=0;
    for (size_t i=0;i<slots;++i) {
        if (index>=slots || (seen[index/8] & (1u<<(index%8)))) fail("not one complete cycle");
        seen[index/8] |= (unsigned char)(1u<<(index%8));
        index=data[index*16];
    }
    free(seen);
    if (index!=0 || chase_cycle(data,slots)!=0) fail("cycle does not return to origin");
    fprintf(stderr,"CORRECTNESS PASS cpu=%d memory_node=%d bytes=%zu slots=%zu expected_sum=%" PRIu64 "\n",
            cpu,node,bytes,slots,expected);
    verify_pages(data,bytes,node,"before",cpu);
    size_t reps[2];
    for (int p=0;p<2;++p) {
        size_t probe=1;
        double elapsed;
        sink=p?chase_cycle(data,slots):scan_sum(data,words);
        while ((elapsed=batch(data,words,slots,p,probe,p?0:expected))<0.06) probe*=2;
        reps[p]=(size_t)((double)probe*0.15/elapsed);
        if (reps[p]<1) reps[p]=1;
        fprintf(stderr,"CALIBRATE pattern=%s reps=%zu\n",p?"chase":"scan",reps[p]);
    }
    for (int round=0;round<rounds;++round) {
        int first=(int)(random_u64()&1u);
        for (int position=0;position<2;++position) {
            int p=(first+position)%2;
            sink=p?chase_cycle(data,slots):scan_sum(data,words);
            int start_cpu=sched_getcpu();
            double elapsed=batch(data,words,slots,p,reps[p],p?0:expected);
            int end_cpu=sched_getcpu();
            if (start_cpu!=cpu || end_cpu!=cpu) fail("CPU placement changed");
            double ns=p?elapsed*1e9/(double)(reps[p]*slots):0;
            double gib=p?0:(double)bytes*(double)reps[p]/elapsed/1073741824.0;
            printf("SAMPLE,%d,%d,%d,%d,%s,%zu,%zu,%zu,%.9f,%.6f,%.6f,%d,%d,1\n",
                   cpu,node,round,position,p?"chase":"scan",bytes,slots,reps[p],elapsed,ns,gib,start_cpu,end_cpu);
            fflush(stdout);
        }
    }
    verify_pages(data,bytes,node,"after",cpu);
    if (munmap(data,bytes)) fail("munmap");
    fprintf(stderr,"BENCH PASS cpu=%d memory_node=%d samples=%d all_checks=pass\n",cpu,node,rounds*2);
    return 0;
}
